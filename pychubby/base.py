"""Base classes and functions."""

import pathlib

import cv2
import numpy as np
import scipy

CACHE_FOLDER = pathlib.Path.home() / '.pychubby/'

CACHE_FOLDER.mkdir(parents=True, exist_ok=True)


class DisplacementField:
    """Represents a coordinate transformation."""

    @classmethod
    def generate(cls, shape, old_points, new_points, anchor_corners=True, **interpolation_kwargs):
        """Create a displacement field based on old and new landmark points.

        Parameters
        ----------
        shape : tuple
            Tuple representing the height and the width of the displacement field.

        old_points : np.ndarray
            Array of shape `(N, 2)` representing the x and y coordinates of the
            old landmark points.

        new_points : np.ndarray
            Array of shape `(N, 2)` representing the x and y coordinates of the
            new landmark points.

        anchor_corners : bool
            If True, then assumed that the 4 corners of the image correspond.

        interpolation_kwargs : dict
            Additional parameters related to the interpolation.

        Returns
        -------
        df : DisplacementField
            DisplacementField instance representing the transformation that
            allows for warping the old image with old landmarks into the new
            coordinate space.

        """
        if not (isinstance(old_points, np.ndarray) and isinstance(new_points, np.ndarray)):
            raise TypeError("The old and new points need to be numpy arrays.")

        if old_points.shape != new_points.shape:
            raise ValueError("The old and new points do not have the same dimensions.")

        points_delta_x = old_points[:, 0] - new_points[:, 0]
        points_delta_y = old_points[:, 1] - new_points[:, 1]

        if anchor_corners:
            corners = np.array([[0, 0],
                                [0, shape[0] - 1],
                                [shape[1] - 1, 0],
                                [shape[1] - 1, shape[0] - 1]])
            new_points = np.vstack([new_points, corners])
            old_points = np.vstack([old_points, corners])
            points_delta_x = np.concatenate([points_delta_x, [0, 0, 0, 0]])
            points_delta_y = np.concatenate([points_delta_y, [0, 0, 0, 0]])

        # Prepare kwargs
        if not interpolation_kwargs:
            interpolation_kwargs = {'function': 'linear'}

        # Fitting
        rbf_x = scipy.interpolate.Rbf(new_points[:, 0], new_points[:, 1], points_delta_x,
                                      **interpolation_kwargs)
        rbf_y = scipy.interpolate.Rbf(new_points[:, 0], new_points[:, 1], points_delta_y,
                                      **interpolation_kwargs)

        # Prediction
        x_grid, y_grid = np.meshgrid(range(shape[1]), range(shape[0]))
        x_grid_r, y_grid_r = x_grid.ravel(), y_grid.ravel()

        delta_x = rbf_x(x_grid_r, y_grid_r).reshape(shape)
        delta_y = rbf_y(x_grid_r, y_grid_r).reshape(shape)

        return cls(delta_x, delta_y)

    def __init__(self, delta_x, delta_y):
        """Construct."""
        if not (isinstance(delta_x, np.ndarray) and isinstance(delta_y, np.ndarray)):
            raise TypeError('The deltas need to be a numpy array.')

        if not (delta_x.ndim == delta_y.ndim == 2):
            raise ValueError('The dimensions of delta_x and delta_y need to be 2.')

        if delta_x.shape != delta_y.shape:
            raise ValueError('The shapes of deltas need to be equal')

        self.shape = delta_x.shape

        self.delta_x = delta_x.astype(np.float32)
        self.delta_y = delta_y.astype(np.float32)

    @property
    def is_valid(self):
        """Check whether both delta_x and delta_y finite."""
        return np.all(np.isfinite(self.delta_x)) and np.all(np.isfinite(self.delta_y))

    @property
    def transformation(self):
        """Compute actual transformation rather then displacements."""
        x, y = np.meshgrid(range(self.shape[1]), range(self.shape[0]))
        transformation_x = self.delta_x + x.astype('float32')
        transformation_y = self.delta_y + y.astype('float32')

        return transformation_x, transformation_y

    def warp(self, img, order=1):
        """Warp image into new coordinate system.

        Parameters
        ----------
        img : np.ndarray
            Image to be warped. Any number of channels and dtype either uint8 or float32.

        order : int
            Interpolation order.
                * 0 - nearest neigbours
                * 1 - linear
                * 2 - cubic

        Returns
        -------
        warped_img : np.ndarray
            Warped image. The same number of channels and same dtype as the `img`.

        """
        tform_x, tform_y = self.transformation
        warped_img = cv2.remap(img, tform_x, tform_y, order)

        return warped_img
