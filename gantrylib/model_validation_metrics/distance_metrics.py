import numpy as np
from scipy.spatial import distance
import warnings
from skimage import measure


def rootMeanSquaredError(P, D):
    """
    Parameters
    ----------
    D : M x N numpy array
        Experimentally obtained Data, as a numpy array of length N,
    
    P : 1 x N numpy array
        Model prediction as a 1 x N numpy array, 
    """
    return np.sqrt(np.mean(np.square(D-P), axis=0))

def normalized_euclidean_metric(P, D, D_std):
    """
    Calculate normalized euclidian metric and return it

    Parameters
    ----------
    D : 1 x N numpy array
        Experimentally obtained Data, as a numpy array of length N,

    D_std : 1 x N numpy array
            Standard deviation of the data, as a numpy array of length N,
    
    P : 1 x N numpy array
        Model prediction as a 1 x N numpy array, 

    Returns
    -------
    d : 1 x N numpy array
        Normalized absolute distance at each point.

    d_ne : scalar
        Total normalized euclidean distance.

    Notes
    -----
    If the standard deviation of the data is not known, the sample standard deviation can be calculated instead.
    In such case, D is the sample mean.

    There also seem to be multiple definitions of the NED, see e.g. https://stats.stackexchange.com/questions/136232/definition-of-normalized-euclidean-distance
    The definition as used in the Sandia Laboratories report is apparantely not the best NED definition, 
    since results can be anywhere, whereas other definitions limit them between 0 and 1, which is better for general purpose comparison.

    From the Sandia report: this metric is a generalization of the absolute value of the z-score. For each datapoint Di,
    d measures the number of standard deviations the point Pi is from the normal distribution centered at Di and std equal to Di_std.
    A value of d_ne < 2 is therefore generally acceptable.
    
    Examples
    --------
    Todo : Complete
    """
    bool_idx = D_std < 0.0001
    excl_idx = (np.where(bool_idx == True))[0]
    if len(excl_idx)>0:
        # best to print the warning and exclude those indexes from being used in the calculation of the metric.
        # since simulations often all start at 0 the first index will often have std = 0
        warnings.warn("Standard deviation is 0 at indexes" + str(excl_idx) + ", ignoring them in calculation, otherwise normalized euclidian distance would be be infinte")
    inv_bool_idx = np.logical_not(bool_idx)
    D = D[inv_bool_idx]
    D_std = D_std[inv_bool_idx]
    P = P[inv_bool_idx]

    d = np.abs(P - D) * 1/D_std # equation 2.7
    d_ne = np.sqrt(np.sum(np.power(d, 2))) # equation 2.8
    
    return d, d_ne

def mahalanobis_distance(P, D):
    """
    Calculate mahalanobis distance and return it

    Parameters
    ----------
    D : M x N numpy array
        Experimentally obtained Data, as a numpy array of length N,
        with M replications per datapoint.
    
    P : 1 x N numpy array
        Model prediction as a 1 x N numpy array.

    Returns
    -------
    d_mahalanobis : scalar
        The mahalanobis distance

    Notes
    -----
    The Mahalanobis distance measures the distance between a point, and a multivariate distribution's mean.
    In this case P, the model prediction, is the point in multivariate space, and D, the experimental data,
    is used to construct the multivariate distribution.

    The mahalanobis distance is given by the formula

    .. math::

        d_{maha} = \sqrt{(P - \mu)^T}S^{-1}(P - \mu)}

    Where :math:`\mu` is the sample mean of D, and S is the sample covariance matrix of D, which'd look like this if D had 3 timestamps:

    +------+-----------+-----------+----------+
    |  S   |   D_t0    |   D_t1    |   D_t2   |
    +------+-----------+-----------+----------+
    | D_t0 | Var(D_t0) | ...       | ...      |
    | D_t1 | ...       | Var(D_t1) | ...      |
    | D_t2 | ...       | ...       | Var(D_t2 |
    +------+-----------+-----------+----------+
    
    Examples
    --------
    Todo : Complete
    """
    D_std = np.std(D, axis=0)
    bool_idx = D_std < 0.0001
    excl_idx = (np.where(bool_idx == True))[0]
    if len(excl_idx)>0:
        # best to print the warning and exclude those indexes from being used in the calculation of the metric.
        # since simulations often all start at 0 the first index will often have std = 0
        warnings.warn("Standard deviation is 0 at indexes" + str(excl_idx) + ", ignoring them in calculation, otherwise normalized covariance matrix is non invertible")
    inv_bool_idx = np.logical_not(bool_idx)
    D = D[:,inv_bool_idx]
    P = P[inv_bool_idx]

    S = np.cov(D, rowvar=False)
    try:
        SI = np.linalg.inv(S)
    except:
        warnings.warn("singular (non-invertible) covariance matrix, could not calculate distance")
        return float('nan')
    mu = np.mean(D, axis=0)
    d_mahalanobis = distance.mahalanobis(P, mu, SI)
    # d_mahalanobis_paired = [distance.mahalanobis(P, d, SI) for d in D.T]
    # d_mahalanobis_avg = np.mean(d_mahalanobis_paired)
    return d_mahalanobis

def mLCSS(P, D, epsilon=0.1):
    """
    Calculate the modified Longest Common Subsequence Similarity between two sequences P and D.
    
    The mLCSS is a similarity measure between two sequences of real numbers, which is based on the Longest Common Sub-sequence (LCSS).
    The mLCSS similarity measure is a matrix of size m x n, where each element M[i, j] is the length of the longest common subsequence of P[0:i] and D[0:j]. Two elements are considered equal if their absolute difference is less than epsilon, that is d(a[i], b[j]) < epsilon.
    The mLCSS-based similarity indicator is defined as the length of the longest common subsequence, divided by the length of the shortest sequence. It is a number between 0 and 1, where 1 indicates that the two sequences are identical, and 0 indicates that they are completely different.

    Parameters
    ----------
    P : 1 x m numpy array
        Model prediction as a 1 x m numpy array, 

    D : 1 x n numpy array
        Experimentally obtained Data, as a numpy array of length n,

    epsilon : float, optional
        The matching threshold, default is 0.1

    Returns
    -------
    M : m x n matrix
        The mLCSS similarity measure

    mLCSS : scalar
        The mLCSS Similarity indicator
    """
    m, n = len(P), len(D)
    M = np.zeros((m + 1, n + 1))

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if abs(P[i - 1] - D[j - 1]) < epsilon:
                M[i, j] = M[i - 1, j - 1] + 1
            else:
                M[i, j] = max(M[i - 1, j], M[i, j - 1])


    lcss_length = M[m, n]
    phi_mLCSS = lcss_length / (min(m, n))
    return phi_mLCSS, M

def DTW(P, D):
    m, n = len(P), len(D)
    # Giovanni does some normalization here, but I don't think it's necessary
    P_max = np.max(P)
    D_max = np.max(D)
    P = P / np.max((P_max, D_max))
    D = D / np.max((P_max, D_max))  
    M = np.full((m+1, n+1), np.inf) # m rows, n columns matrix
    M[0, 0] = 0

    DM =  np.zeros((m, n))
    for i in range(m):
        for j in range(n):
            DM[i, j] = abs(P[i] - D[j])

    for i in range(1, m+1):
        for j in range(1, n+1):
            cost = abs(P[i-1] - D[j-1])
            M[i, j] = cost + min(M[i-1, j], # insertion
                                M[i, j-1],  # deletion
                                M[i-1, j-1]) # match

    # backtracking for optimal path
    i, j = m, n
    path = [(i-1, j-1)] # bottom (or top) right corner is first element

    while i > 1 or j > 1:
        # Get the index of the minimum cost move
        steps = [
            (i-1, j-1),  # Move diagonally (match)
            (i-1, j),   # Move up (insertion)
            (i, j-1)   # Move left (deletion)
        ]
        costs = [M[r, c] for r, c in steps]
        min_index = np.argmin(costs)
        i, j = steps[min_index]
        path.append((i-1, j-1))

    path.reverse()  # Reverse to start from the beginning

    # if the paths overlap completely, the distance is 0
    # we do take the mean of the distances to get a mean distance
    phi_DTW = 1 - M[m,n] / max(m, n)
    return phi_DTW, M[1:,1:], path

# reference: sakoe et al.

def frechet_distance(P, D):
    """
    Calculate the Frechet distance between two curves P and D.

    The Frechet distance is a measure of similarity between two curves, which is based on the idea of a "walk" along the curves.
    The Frechet distance is the minimum length of a leash that allows a person and a dog to walk along their respective curves without ever getting too far apart.
    The Frechet distance is a measure of similarity between two curves, which is based on the idea of a "walk" along the curves.
    The Frechet distance is the minimum length of a leash that allows a person and a dog to walk along their respective curves without ever getting too far apart.

    Parameters
    ----------
    P : M x 2 numpy array
        Model prediction as a M x 2 numpy array, where M is the number of points in the curve.

    D : N x 2 numpy array
        Experimentally obtained Data, as a N x 2 numpy array, where N is the number of points in the curve.

    Returns
    -------
    d_frechet : scalar
        The Frechet distance between the two curves.
    """
    


def weak_frechet_distance(P, D):
    """Also non-monotone frechet distance

    Args:
        P (_type_): _description_
        D (_type_): _description_
    """
    pass

def _c(ca, i, j, p, q):
    if ca[i, j] > -1:
        return ca[i, j]
    elif i == 0 and j == 0:
        ca[i, j] = np.linalg.norm(p[0]-q[0])
    elif i > 0 and j == 0:
        ca[i, j] = max(_c(ca, i - 1, 0, p, q), np.linalg.norm(p[i]-q[0]))
    elif i == 0 and j > 0:
        ca[i, j] = max(_c(ca, 0, j - 1, p, q), np.linalg.norm(p[0]-q[j]))
    elif i > 0 and j > 0:
        ca[i, j] = max(min(_c(ca, i - 1, j, p, q),
                           _c(ca, i - 1, j - 1, p, q),
                           _c(ca, i, j - 1, p, q)),
                       np.linalg.norm(p[i]-q[j]))
    else:
        ca[i, j] = float('inf')
    return ca[i, j]

def discrete_frechet_distance(P, Q):
    len_P = len(P)
    len_Q = len(Q)

    ca = np.ones((len_P, len_Q)) * -1
    return _c(ca, len_P - 1, len_Q - 1, P, Q)

def discrete_weak_frechet_distance(X1, Y1, X2, Y2, res=None):
    """Discrete weak frechet distance

    adapted to Python from this Matlab script: https://nl.mathworks.com/matlabcentral/fileexchange/41956-frechet-distance-calculator

    Args:
        X1 ([float]): Vector of x-coordinates of the first curve
        Y1 ([float]): Vector of y-coordinates of the first curve
        X2 ([float]): Vector of x-coordinates of the second curve
        Y2 ([float]): Vector of y-coordinates of the second curve
        res (float, optional): Resolution parameter. Defaults to None, in which case a good value is computed.

    Raises:
        ValueError: _description_
    """
    # Inputs are expected to be 1D vectors, but we need to make sure they are 2D row vectors
    # check if input vectors are 1D
    if len(X1.shape) > 1 or len(Y1.shape) > 1 or len(X2.shape) > 1 or len(Y2.shape) > 1:
        raise ValueError("Input vectors must be 1D")
    # reshape input vectors to 2D row vectors
    X1 = np.array(X1).reshape(-1, 1)
    Y1 = np.array(Y1).reshape(-1, 1)
    X2 = np.array(X2).reshape(-1, 1)
    Y2 = np.array(Y2).reshape(-1, 1)

    # get path point length
    L1 = len(X1)
    L2 = len(X2)

    # check vector lengths
    if L1 != len(Y1) or L2 != len(Y2):
        raise ValueError("Paired input vectors (Xi, Yi) must have the same length")
    
    # create matrix forms
    X1_mat = np.ones((L2, 1))*X1.T
    Y1_mat = np.ones((L2, 1))*Y1.T
    X2_mat = X2*np.ones((1, L1))
    Y2_mat = Y2*np.ones((1, L1))

    # calculate the frechet distance matrix
    frechet1 = np.sqrt((X1_mat - X2_mat)**2 + (Y1_mat - Y2_mat)**2)
    fmin = np.min(frechet1)
    fmax = np.max(frechet1)

    # handle resolution
    if res is not None:
        if res <= 0:
            warnings.warn("Resolution parameter must be greater than zero")
        elif ((fmax - fmin) / res) > 10000:
            warnings.warn('Given these two curves, and that resolution, this might take a while.')
        elif res >= (fmax - fmin):
            warnings.warn('The resolution is too low given these curves to compute anything meaningful.')
            f=fmax
            return f
    else:
        res = (fmax - fmin)/1000

    # compute the frechet distance
    for q3 in np.arange(fmin, fmax, res):
        im1 = measure.label(frechet1 <= q3)
    
        # get region number of beginning and end points
        if im1[0,0] != 0 and im1[0,0] == im1[-1, -1]:
            f = q3
            break
    
    return f

if __name__ == "__main__":
    X1 = np.array([1,2,3])
    Y1 = np.array([1,2,3])
    X2 = np.array([1,2,3,4])
    Y2 = np.array([1,1,1,1])
    discrete_weak_frechet_distance(X1, Y1, X2, Y2)