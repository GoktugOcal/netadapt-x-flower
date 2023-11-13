import os
import ujson
import numpy as np
import gc
from sklearn.model_selection import train_test_split
from non_iid_generator.customDataset import CustomDataset
import pickle
from torchvision.transforms import transforms
from PIL import Image
import h5py

batch_size = 10
train_size = 0.75 # merge original training set and test set, then split it manually. 
least_samples = batch_size / (1-train_size) # least samples for each client
alpha = 0.5 # for Dirichlet distribution
# alpha = 1.0 # for Dirichlet distribution

def check(config_path, train_path, test_path, server_path, num_clients, num_classes, niid=False, 
        balance=True, partition=None):
    # check existing dataset
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = ujson.load(f)
        if config['num_clients'] == num_clients and \
            config['num_classes'] == num_classes and \
            config['non_iid'] == niid and \
            config['balance'] == balance and \
            config['partition'] == partition and \
            config['alpha'] == alpha and \
            config['batch_size'] == batch_size:
            print("\nDataset already generated.\n")
            return True

    dir_path = os.path.dirname(train_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    dir_path = os.path.dirname(test_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    dir_path = os.path.dirname(server_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    return False

def separate_data(data, num_clients, num_classes, niid=False, balance=False, partition=None, class_per_client=2):
    X = [[] for _ in range(num_clients)]
    y = [[] for _ in range(num_clients)]
    statistic = [[] for _ in range(num_clients)]

    dataset_content, dataset_label = data

    dataidx_map = {}

    if not niid:
        partition = 'pat'
        class_per_client = num_classes

    if partition == 'pat':
        idxs = np.array(range(len(dataset_label)))
        idx_for_each_class = []
        for i in range(num_classes):
            idx_for_each_class.append(idxs[dataset_label == i])

        class_num_per_client = [class_per_client for _ in range(num_clients)]
        for i in range(num_classes):
            selected_clients = []
            for client in range(num_clients):
                if class_num_per_client[client] > 0:
                    selected_clients.append(client)
                selected_clients = selected_clients[:int(np.ceil((num_clients/num_classes)*class_per_client))]

            num_all_samples = len(idx_for_each_class[i])
            num_selected_clients = len(selected_clients)
            num_per = num_all_samples / num_selected_clients
            if balance:
                num_samples = [int(num_per) for _ in range(num_selected_clients-1)]
            else:
                num_samples = np.random.randint(max(num_per/10, least_samples/num_classes), num_per, num_selected_clients-1).tolist()
            num_samples.append(num_all_samples-sum(num_samples))

            idx = 0
            for client, num_sample in zip(selected_clients, num_samples):
                if client not in dataidx_map.keys():
                    dataidx_map[client] = idx_for_each_class[i][idx:idx+num_sample]
                else:
                    dataidx_map[client] = np.append(dataidx_map[client], idx_for_each_class[i][idx:idx+num_sample], axis=0)
                idx += num_sample
                class_num_per_client[client] -= 1

    elif partition == "dir":
        # https://github.com/IBM/probabilistic-federated-neural-matching/blob/master/experiment.py
        min_size = 0
        K = num_classes
        N = len(dataset_label)

        while min_size < num_classes:
            idx_batch = [[] for _ in range(num_clients)]
            for k in range(K):
                idx_k = np.where(dataset_label == k)[0]
                np.random.shuffle(idx_k)
                proportions = np.random.dirichlet(np.repeat(alpha, num_clients))
                proportions = np.array([p*(len(idx_j)<N/num_clients) for p,idx_j in zip(proportions,idx_batch)])
                proportions = proportions/proportions.sum()
                proportions = (np.cumsum(proportions)*len(idx_k)).astype(int)[:-1]
                idx_batch = [idx_j + idx.tolist() for idx_j,idx in zip(idx_batch,np.split(idx_k,proportions))]
                min_size = min([len(idx_j) for idx_j in idx_batch])

        for j in range(num_clients):
            dataidx_map[j] = idx_batch[j]
    else:
        raise NotImplementedError

    # assign data
    for client in range(num_clients):
        idxs = dataidx_map[client]
        X[client] = dataset_content[idxs]
        y[client] = dataset_label[idxs]

        for i in np.unique(y[client]):
            statistic[client].append((int(i), int(sum(y[client]==i))))
            

    del data
    # gc.collect()

    for client in range(num_clients):
        print(f"Client {client}\t Size of data: {len(X[client])}\t Labels: ", np.unique(y[client]))
        print(f"\t\t Samples of labels: ", [i for i in statistic[client]])
        print("-" * 50)

    return X, y, statistic


def split_data(X, y):
    # Split dataset
    train_data, test_data = [], []
    num_samples = {'train':[], 'test':[]}

    for i in range(len(y)):
        X_train, X_test, y_train, y_test = train_test_split(
            X[i], y[i], train_size=train_size, shuffle=True)

        train_data.append({'x': X_train, 'y': y_train})
        num_samples['train'].append(len(y_train))
        test_data.append({'x': X_test, 'y': y_test})
        num_samples['test'].append(len(y_test))

    print("Total number of samples:", sum(num_samples['train'] + num_samples['test']))
    print("The number of train samples:", num_samples['train'])
    print("The number of test samples:", num_samples['test'])
    print()
    del X, y
    # gc.collect()

    return train_data, test_data

def save_file(config_path, train_path, test_path, train_data, test_data, num_clients, 
                num_classes, statistic, transform, niid=False, balance=True, partition=None):
    config = {
        'num_clients': num_clients, 
        'num_classes': num_classes, 
        'non_iid': niid, 
        'balance': balance, 
        'partition': partition, 
        'Size of samples for labels in clients': statistic, 
        'alpha': alpha, 
        'batch_size': batch_size, 
    }

    # gc.collect()
    print("Saving to disk.\n")

    # transform=transforms.Compose([
    #     transforms.RandomCrop(32, padding=4), 
    #     transforms.Resize(224),
    #     transforms.RandomHorizontalFlip(),
    #     transforms.ToTensor(),
    #     transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010))
    # ])

    for idx, train_dict in enumerate(train_data):        
        data = train_dict["x"]
        labels = train_dict["y"]
        custom_dataset = CustomDataset(data, labels, transform=transform)
        with open(train_path + str(idx) + '.pkl', 'wb') as f:
            pickle.dump(custom_dataset, f)

    for idx, test_dict in enumerate(test_data):
        data = test_dict["x"]
        labels = test_dict["y"]
        custom_dataset = CustomDataset(data, labels, transform=transform)
        with open(test_path + str(idx) + '.pkl', 'wb') as f:
            pickle.dump(custom_dataset, f)
            
    with open(config_path, 'w') as f:
        ujson.dump(config, f)

    print("Finish generating dataset.\n")

def save_file_org(config_path, train_path, test_path, train_data, test_data, num_clients, 
                num_classes, statistic, niid=False, balance=True, partition=None):
    config = {
        'num_clients': num_clients, 
        'num_classes': num_classes, 
        'non_iid': niid, 
        'balance': balance, 
        'partition': partition, 
        'Size of samples for labels in clients': statistic, 
        'alpha': alpha, 
        'batch_size': batch_size, 
    }

    # gc.collect()
    print("Saving to disk.\n")

    for idx, train_dict in enumerate(train_data):
        with open(train_path + str(idx) + '.npz', 'wb') as f:
            np.savez_compressed(f, data=train_dict)
    for idx, test_dict in enumerate(test_data):
        with open(test_path + str(idx) + '.npz', 'wb') as f:
            np.savez_compressed(f, data=test_dict)
    with open(config_path, 'w') as f:
        ujson.dump(config, f)

    print("Finish generating dataset.\n")

def split_server_data(initial_train_image, initial_train_label, split_idx, transform):

    X_train, X_test, y_train, y_test = train_test_split(
            initial_train_image,
            initial_train_label,
            train_size=0.75,
            shuffle=True)

    train_dataset = CustomDataset(X_train, y_train, transform=transform)
    test_dataset = CustomDataset(X_test, y_test, transform=transform)
    
    # train_data = {'x': X_train, 'y': y_train}
    # test_data = {'x': X_test, 'y': y_test}

    print("Initial training dataset for server have been created.")
    return train_dataset, test_dataset
    
def server_data_save(server_path, train_dataset, test_dataset):

    with open(server_path + "train" + '.pkl', 'wb') as f:
        pickle.dump(train_dataset, f)
    
    with open(server_path + "test" + '.pkl', 'wb') as f:
        pickle.dump(test_dataset, f)

    # with open(server_path + "train" + '.npz', 'wb') as f:
    #     np.savez_compressed(f, data=train_dataset)
    # with open(server_path + "train" + '.npy', 'wb') as f:
    #     np.save(f, train_dataset, allow_pickle=True)
    # with h5py.File(server_path + "train" + '.hdf5', 'w') as f:
    #     f.create_dataset("x", train_dataset["x"], dtype="int8")
    #     f.create_dataset("y", train_dataset["y"], dtype="int8")

    # with open(server_path + "test" + '.npz', 'wb') as f:
    #     np.savez_compressed(f, data=test_dataset)
    # with open(server_path + "test" + '.npy', 'wb') as f:
    #     np.save(f, test_dataset, allow_pickle=True)
    # with h5py.File(server_path + "test" + '.hdf5', 'w') as f:
    #     f.create_dataset("data", test_dataset)
    

    
    print("Initial training dataset for server have been saved.")

# def save_file(config_path, train_path, test_path, train_data, test_data, num_clients, 
#                 num_classes, statistic, niid=False, balance=True, partition=None):
#     config = {
#         'num_clients': num_clients, 
#         'num_classes': num_classes, 
#         'non_iid': niid, 
#         'balance': balance, 
#         'partition': partition, 
#         'Size of samples for labels in clients': statistic, 
#         'alpha': alpha, 
#         'batch_size': batch_size, 
#     }

#     # gc.collect()
#     print("Saving to disk.\n")

#     for idx, train_dict in enumerate(train_data):
#         with open(train_path + str(idx) + '.npz', 'wb') as f:
#             np.savez_compressed(f, data=train_dict)
#     for idx, test_dict in enumerate(test_data):
#         with open(test_path + str(idx) + '.npz', 'wb') as f:
#             np.savez_compressed(f, data=test_dict)
#     with open(config_path, 'w') as f:
#         ujson.dump(config, f)

#     print("Finish generating dataset.\n")