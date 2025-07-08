import warnings
import numpy as np
from scipy import stats

def calculate_reliability_metric(X, y, e, c, clt=True):
    """Calculate univariate reliability metric and return it.

    Parameters
    ----------
    X : numpy array
        The replicated experimental measurements.
    
    y : int or double
        Model prediction.
    
    e : int or double
        Interval bounds.

    c : int or double
        Confidence requirement.
    
    clt : bool, default=True
        Whether or not the normality assumption of the Central Limit Theorem may be applied. When False, bootstrapping is used to infer the reliability metric.

    Returns
    -------
    r : double
        The reliability metric, it's the probability that D falls in the interval [-e, e]
    
    accept : bool
        Acceptance of P in relation to c: 1 when accepted, 0 when rejected

    Notes
    -----
    The reliability metric is a model validation metric that estimates the probability
    that the difference between model and experimental observation falls within the interval [-e, e].
    This value, let's call it r, can be compared with the confidence requirement to accept or reject the model.

    In mathematical terms, the following equation is checked: 
    
    .. math:: P(|\overline{X} - y_0| < e)>c

    With the assumption that X follows a normal distribution 
    
    .. math:: N(\overline{x}, s/\sqrt{n})

    Todo complete further

    Examples
    --------

    Todo complete further
    
    """
    n = X.size

    if n < 30 and clt == True:
        warnings.warn("When X is less than 30 the central limit theorem normality assumption may not hold. Consider specifying parameter 'clt' as False.")

    if clt == True:
        # calculate relibaility metric with Central Limit Theorem assumption of normality
        X_overlined = np.mean(X) # calculate sample mean of X
        s = np.std(X, ddof=1) # calculate sample standard deviation of X

        std_err = s/np.sqrt(n) # calculate standard error

        Phi_right = stats.norm.cdf(1/std_err * (e - np.abs(X_overlined - y))) # Phi = cdf of standard normal distribution/
        Phi_left = stats.norm.cdf(1/std_err * (-e - np.abs(X_overlined - y)))

        r = Phi_right - Phi_left
        accept = r > c

        return r, accept
    else:
        # clt == False
        # calculate reliability metric with bootstrapping
        r = 0
        rng = np.random.default_rng()

        resamples = 5000

        X_resample = rng.choice(X, (resamples, n))
        r = np.mean(np.abs(np.mean(X_resample, axis=1) - y) < e)
        
        accept = r > c

        return r, accept
