CUDA_VISIBLE_DEVICES=0 python federated_master.py models/alexnet/fed/core_1_prune-by-mac 3 224 224 \
    -im models/alexnet/model_pt21.pth.tar -gp 0 1 2 3 4 5 6 \
    -mi 10 -bur 0.25 -rt FLOPS  -irr 0.025 -rd 0.96 \
    -lr 0.001 -st 500 \
    -dp data/ --arch alexnet