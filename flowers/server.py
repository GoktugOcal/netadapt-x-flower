from typing import List, Tuple
from copy import deepcopy
import json

import flwr as fl
from flwr.common import (
    EvaluateIns,
    EvaluateRes,
    FitIns,
    FitRes,
    MetricsAggregationFn,
    Metrics,
    NDArrays,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.common.logger import log
from flwr.server.strategy.aggregate import aggregate, weighted_loss_avg
from flwr.server.strategy import Strategy

from flwr.server.strategy import FedAvg
from flwr.common.typing import Parameters, Scalar, FitIns, FitRes
from flwr.server.client_proxy import ClientProxy
from flwr.server.client_manager import ClientManager

from logging import WARNING
from typing import Callable, Dict, List, Optional, Tuple, Union

# Define metric aggregation function
def weighted_average(metrics: List[Tuple[int, Metrics]]) -> Metrics:
    # Multiply accuracy of each client by number of examples used
    accuracies = [num_examples * m["accuracy"] for num_examples, m in metrics]
    examples = [num_examples for num_examples, _ in metrics]

    # Aggregate and return custom metric (weighted average)
    return {"accuracy": sum(accuracies) / sum(examples)}


class NetStrategy(FedAvg):

    def __init__(
        self,
        network_arch
    ) -> None:
        super().__init__()
        self.network_arch = network_arch
        self.network_arch_str = self.network_arch

    def configure_fit(
        self, server_round: int, parameters: Parameters, client_manager: ClientManager
    )    -> List[Tuple[ClientProxy, FitIns]]:
        """Configure the next round of training."""

        # Sample clients
        sample_size, min_num_clients = self.num_fit_clients(
            client_manager.num_available()
        )

        clients = client_manager.sample(
            num_clients=sample_size, min_num_clients=min_num_clients
        )
        print("############ GOKTUG - serverside ############")

        cfg_fit = []
        for cli in clients:
            print(cli)
            config = {"network_arch" : self.network_arch_str}

            fit_ins = FitIns(parameters, deepcopy(config))
            # append
            cfg_fit.append((cli, fit_ins))
        return cfg_fit

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        """Aggregate fit results using weighted average."""
        parameters_aggregated, metrics_aggregated = super().aggregate_fit(
            server_round=server_round, results=results, failures=failures
        )

        self.parameters_aggregated = parameters_to_ndarrays(parameters_aggregated)
        self.metrics_aggregated = metrics_aggregated

        return parameters_aggregated, metrics_aggregated
    
    def evaluate(
        self, server_round: int, parameters: Parameters
    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        """Evaluate model parameters using an evaluation function."""
        if self.evaluate_fn is None:
            # No evaluation function provided
            return None
        parameters_ndarrays = parameters_to_ndarrays(parameters)
        eval_res = self.evaluate_fn(server_round, parameters_ndarrays, {})
        if eval_res is None:
            return None
        loss, metrics = eval_res
        print("Evaluation done.")
        return loss, metrics


def flower_server_execute(strategy):
    fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=1),
        strategy=strategy,
    )