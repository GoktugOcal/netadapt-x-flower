python test_master.py \
    models/alexnet/test/test-32-NIID-20c \
    3 32 32 \
    -im models/alexnet/alexnet32_server.pth.tar -gp 0 \
    -mi 10 -bur 0.25 -rt FLOPS -irr 0.025 -rd 0.5 \
    -lr 0.001 -st 500 \
    -dp data/ --arch alexnet \
    -nc 0