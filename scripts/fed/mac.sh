python federated_master.py \
    models/alexnet/fed/test-cpu-10nc-mac \
    3 224 224 \
    -im models/alexnet/model_cpu.pth.tar -gp 0 \
    -mi 10 -bur 0.25 -rt FLOPS -irr 0.025 -rd 0.96 \
    -lr 0.001 -st 500 \
    -dp data/Cifar10/server --arch alexnet \
    -nc 10