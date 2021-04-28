import torch
from torch import nn

import numpy as np
from scipy.signal import find_peaks, find_peaks_cwt, peak_prominences, peak_widths
from scipy.ndimage import gaussian_filter1d


class PhoenixEmulator(nn.Module):
    r"""
    A PyTorch layer that clones precomputed synthetic spectra

    """

    def __init__(self):
        super().__init__()

        # Read in the synthetic spectra at native resolution
        # self.wl_native, self.flux_native = self.read_native_PHOENIX_model(4700, 4.5)

        (lam_centers, prominences, widths) = identify_lines_in_native_model()

        self.amplitudes = nn.Parameter(
            torch.log(amplitudes).clone().detach().requires_grad_(True)
        )
        self.widths = nn.Parameter(
            np.log(widths_angs).clone().detach().requires_grad_(True)
        )

        # Fix the wavelength centers as gospel for now.
        self.lam_centers = nn.Parameter(
            lam_centers.clone().detach().requires_grad_(False)
        )

        self.teff = nn.Parameter(
            torch.tensor(0, requires_grad=True, dtype=torch.float64)
        )

        self.a_coeff = nn.Parameter(
            torch.tensor(1.0, requires_grad=True, dtype=torch.float64)
        )
        self.b_coeff = nn.Parameter(
            torch.tensor(0.0, requires_grad=True, dtype=torch.float64)
        )
        self.c_coeff = nn.Parameter(
            torch.tensor(0.0, requires_grad=True, dtype=torch.float64)
        )

    def forward(self, wl):
        """The forward pass of the spectral model

        Returns:
            (torch.tensor): the 1D generative spectral model destined for backpropagation parameter tuning
        """

        net_spectrum = 1 - lorentzian_line(
            self.lam_centers.unsqueeze(1),
            torch.exp(self.widths).unsqueeze(1),
            torch.exp(self.amplitudes).unsqueeze(1),
            wl.unsqueeze(0),
        ).sum(0)

        wl_normed = (wl - 10_500.0) / 2500.0
        modulation = (
            self.a_coeff + self.b_coeff * wl_normed + self.c_coeff * wl_normed ** 2
        )

        return net_spectrum * self.black_body(self.teff, wl) * modulation

    def black_body(self, Teff, wavelengths):
        """Make a black body spectrum given Teff and wavelengths
        
        Args:
            Teff (torch.tensor scalar): the natural log of a scalar multiplied by 4700 K to get Teff
        Returns:
            (torch.tensor): the 1D smooth Black Body model normalized to roughly 1 for 4700 K
        -----
        """
        unnormalized = (
            1
            / (wavelengths / 10_000) ** 5
            / (
                torch.exp(
                    1.4387752e-2 / (wavelengths * 1e-10 * (4700.0 * torch.exp(Teff)))
                )
                - 1
            )
        )
        return unnormalized * 20.0

    def identify_lines_in_native_model(self, wl_native, flux_native):
        """Identify the spectral lines in the native model
        
        Args:
            wl_native (torch.tensor vector): The 1D vector of native model wavelengths (Angstroms)
            flux_native (torch.tensor vector): The 1D vector of native model fluxes (Normalized)
        Returns:
            (tuple of tensors): The wavelength centers, prominences, and widths for all ID'ed spectral lines
        -----
        """
        peaks, _ = find_peaks(-flux_native, distance=10, prominence=0.03)
        prominence_data = peak_prominences(-flux_native, peaks)
        width_data = peak_widths(-flux_native, peaks, prominence_data=prominence_data)
        lam_centers = wl_native[peaks]
        prominences = prominence_data[0]
        widths = width_data[0]
        d_lam = np.diff(wl_native)[peaks]
        # Convert FWHM in pixels to Gaussian sigma in Angstroms
        widths_angs = torch.tensor(widths * d_lam / 2.355)

        return (lam_centers, prominences, widths)

    def lorentzian_line(self, lam_center, width, amplitude, wavelengths):
        """Return a Lorentzian line, given properties"""
        return (
            amplitude
            / 3.141592654
            * width
            / (width ** 2 + (wavelengths - lam_center) ** 2)
        )

