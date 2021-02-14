"""
Utility functions and helpers
"""

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.spatial.distance import pdist, squareform
from zipfile import ZipFile
from io import BytesIO
from urllib.request import urlopen

__all__ = [
    "create_sub_by_item_matrix",
    "get_size_in_mb",
    "get_sparsity",
    "nanpdist",
    "create_train_test_mask",
]


def create_sub_by_item_matrix(df, columns=None, force_float=True, errors="raise"):

    """Convert a pandas long data frame of a single rating into a subject by item matrix

    Args:
        df (Dataframe): input dataframe
        columns (list): list of length 3 with dataframe columns to use for reshaping. The first value should reflect unique individual identifier ("Subject"), the second a unique item identifier ("Item", "Timepoint"), and the last the rating made by the individual on that item ("Rating"). Defaults to ["Subject", "Item", "Rating"]
        force_float (bool): force the resulting output to be float data types with errors being set to NaN; Default True
        errors (string): how to handle errors in pd.to_numeric; Default 'raise'

    Return:
        pd.DataFrame: user x item rating Dataframe

    """

    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be pandas instance")
    if columns is None:
        columns = ["Subject", "Item", "Rating"]
    if not all([x in df.columns for x in columns]):
        raise ValueError(
            f"df is missing some or all of the following columns: {columns}"
        )

    ratings = df[columns]
    ratings = ratings.pivot(index=columns[0], columns=columns[1], values=columns[2])
    try:
        if force_float:
            ratings = ratings.apply(pd.to_numeric, errors=errors)
    except ValueError as e:
        print(
            "Auto-converting data to floats failed, probably because you have non-numeric data in some rows. You can set errors = 'coerce' to set these failures to NaN"
        )
        raise (e)

    return ratings


def get_size_in_mb(arr):
    """Calculates size of ndarray in megabytes"""
    if isinstance(arr, (np.ndarray, csr_matrix)):
        return arr.data.nbytes / 1e6
    else:
        raise TypeError("input must by a numpy array or scipy csr sparse matrix")


def get_sparsity(arr):
    """Calculates sparsity of ndarray (0 - 1)"""
    if isinstance(arr, (np.ndarray)):
        return 1 - (np.count_nonzero(arr) / arr.size)
    else:
        raise TypeError("input must be a numpy array")


# Can try to speed this up with numba, but lose support for pandas and scipy so we'd have to rewrite distance functions in numpy/python
def nanpdist(arr, metric="euclidean", return_square=True):
    """
    Just like scipy.spatial.distance.pdist or sklearn.metrics.pairwise_distances, but respects NaNs by only comparing the overlapping values from pairs of rows.

    Args:
        arr (np.ndarray): 2d array
        metric (str; optional): distance metric to use. Must be supported by scipy
        return_square (boo; optional): return a symmetric 2d distance matrix like sklearn instead of a 1d vector like pdist; Default True

    Return:
        np.ndarray: symmetric 2d array of distances
    """

    has_nans = pd.DataFrame(arr).isnull().any().any()
    if not has_nans:
        out = pdist(arr, metric=metric)
    else:
        nrows = arr.shape[0]
        out = np.zeros(nrows * (nrows - 1) // 2, dtype=float)
        mask = np.isfinite(arr)
        vec_mask = np.zeros(arr.shape[1], dtype=bool)
        k = 0
        for row1_idx in range(nrows - 1):
            for row2_idx in range(row1_idx + 1, nrows):
                vec_mask = np.logical_and(mask[row1_idx], mask[row2_idx])
                masked_row1, masked_row2 = (
                    arr[row1_idx][vec_mask],
                    arr[row2_idx][vec_mask],
                )
                out[k] = pdist(np.vstack([masked_row1, masked_row2]), metric=metric)
                k += 1

    if return_square:
        if out.ndim == 1:
            out = squareform(out)
    else:
        if out.ndim == 2:
            out = squareform(out)
    return out


def create_train_test_mask(data, n_train_items=0.1):
    """
    Given a pandas dataframe create a boolean mask such that n_train_items columns are `True` and the rest are `False`. Critically, each row is masked independently. This function does not alter the input dataframe.

    Args:
        data (pd.DataFrame): input dataframe
        n_train_items (float, optional): if an integer is passed its raw value is used. Otherwise if a float is passed its taken to be a (rounded) percentage of the total items. Defaults to 0.1 (10% of the columns of data).

    Raises:
        TypeError: [description]

    Returns:
        pd.DataFrame: boolean dataframe of same shape as data
    """

    if data.isnull().any().any():
        raise ValueError("data already contains NaNs and further masking is ambiguous!")

    if isinstance(n_train_items, (float, np.floating)) and 1 >= n_train_items > 0:
        n_train_items = int(np.round(data.shape[1] * n_train_items))

    elif isinstance(n_train_items, (int, np.integer)):
        n_train_items = n_train_items

    else:
        raise TypeError(
            f"n_train_items must be an integer or a float between 0-1, not {type(n_train_items)} with value {n_train_items}"
        )

    n_test_items = data.shape[1] - n_train_items
    mask = np.array([True] * n_train_items + [False] * n_test_items)
    mask = np.vstack(
        [
            np.random.choice(mask, replace=False, size=mask.shape)
            for _ in range(data.shape[0])
        ]
    )
    return pd.DataFrame(mask, index=data.index, columns=data.columns)


def load_movielens():
    """Download and create a dataframe from the 100k movielens dataset"""
    url = "http://files.grouplens.org/datasets/movielens/ml-100k.zip"
    # With python context managers we don't need to save any temporary files
    print("Getting movielens...")
    with urlopen(url) as resp:
        with ZipFile(BytesIO(resp.read())) as myzip:
            with myzip.open("ml-100k/u.data") as myfile:
                df = pd.read_csv(
                    myfile,
                    delimiter="\t",
                    names=["Subject", "Item", "Rating", "Timestamp"],
                )
    return df
