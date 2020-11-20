"""
datasets
--------

This utility loads 1D echelle data, inheriting from the PyTorch Dataset model.
We currently only support data from the HPF spectrograph.

HPFDataset
############
"""

import torch
from torch.utils.data import Dataset
from astropy.io import fits
import pandas as pd
import numpy as np


# custom dataset loader
class HPFDataset(Dataset):
    r"""Read in an HPF spectrum

    Args:
        filename (list): the Goldilocks echelle spectrum to read-in
        device (str): On which device to house the data, "cuda" or "cpu"

    """

    def __init__(self, filename, device="cuda"):
        super().__init__()
        self.filename = filename
        self.n_pix = 2048
        self.n_orders = 28
        self.n_slices = 9
        hdus = fits.open(filename)
        self.hdus = hdus

        data_cube = []
        for i in range(1, self.n_slices + 1):
            data_cube.append(hdus[i].data.astype(np.float64))

        self.data_cube = torch.tensor(data_cube)

        self.df = self.get_goldilocks_dataframe(filename)

        self.wl = torch.tensor(self.df["Sci Wavl"], device=device, dtype=torch.float64)
        self.flux = torch.tensor(
            self.df["Sci Flux"], device=device, dtype=torch.float64
        )
        self.unc = torch.tensor(
            self.df["Sci Error"], device=device, dtype=torch.float64
        )
        self.order = torch.tensor(self.df["order"], device=device, dtype=torch.int16)

    def __getitem__(self, index):
        """We currently do not use the index"""
        return (self.wl, self.flux, self.unc)

    def __len__(self):
        return 1

    def get_goldilocks_dataframe(self, filename):
        """Return a pandas Dataframe given a Goldilocks FITS file name"""
        df = pd.DataFrame()
        for j in range(self.n_orders):
            df_i = pd.DataFrame()
            for i in range(1, 10):
                name = self.hdus[i].name
                df_i[name] = self.hdus[i].data[j, :]
            df_i["order"] = j
            df = df.append(df_i, ignore_index=True)
        keep_mask = df[df.columns[0:6]] != 0.0
        df = df[keep_mask.all(axis=1)].reset_index(drop=True)

        return df
