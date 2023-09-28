import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image


class CustomDataset(Dataset):
    def __init__(self, data, labels, transform=None):
        self.data = data
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        img = self.data[idx]
        np_img = np.array(img, dtype = np.uint8)
        img = Image.fromarray(np_img, "RGB")

        if self.transform is not None:
            img = self.transform(img)
            # print(type(img))

        class_id = torch.tensor([self.labels[idx]])

        return img, class_id

        # sample = {
        #     'data': img,
        #     'label': self.labels[idx]
        # }
        
        # return sample