import numpy as np
from scipy import stats
from scipy.interpolate import interp1d
from functools import reduce
import warnings

def calculate_frequentist_metric(X, y, alpha=0.05):
    """
    Calculate frequentist validation metric and return it

    Parameters
    ----------
    X : numpy array
        The replicated experimental measurements.
    
    y : int or double
        Model prediction.
    
    alpha : double, default=0.05
        Significance level.

    Returns
    -------
    mu_interval : numpy array
        Interval of true mean mu with (1-alpha)*100% confidence given as a numpy array [lower_boubd, upper_bound].

    E_interval : numpy array
        Interval of true error with (1-alpha)*100% confidence given as a numpy array [lower_bound, upper_bound].
    
    Notes
    -----
    Todo: Complete


    Examples
    --------
    Todo : Complete
    """
    n = X.size

    X_overlined = np.mean(X) # sample mean of X
    s = np.std(X, ddof=1) # sample standard deviation of X
    E_estimated = y - X_overlined # estimated error
    dof = n-1 # degrees of freedom (v) for t table lookup
    t_alpha_div_2_v = stats.t.ppf(1-alpha/2, dof) # T value for 1-alpha confidence

    tmp = t_alpha_div_2_v * s/np.sqrt(n) # temporary variable to store the +/- term for the confidence interval
    conf_interval = np.array([-tmp, tmp]) # double sided confidence interval on experimental data.
    #mu_interval = np.array([X_overlined - tmp, X_overlined + tmp]) # interval of true mean with (1-alpha)*100% confidence
    #E_interval = np.array([E_estimated - tmp, E_estimated + tmp])

    return X_overlined, E_estimated, conf_interval

def calculate_frequentist_metric_interpolated(X, y, alpha=0.05):
    """
    Calculate frequentist validation metric with interpolation and return it

    Parameters
    ----------
    X : List of 2xN numpy array
        The replicated experimental measurements. Assumed to be a list of at least two 2xN numpy arrays, in which
        the first row represents x and the second f(x). Each numpy array in the list may have a different length N,
        and the values may be spaced at random, but x_0 and x_end of the final interpolation will be the intersection
        of the various arrays in X and the single array in y, therefore if all datapoints must be used, ensure x_0 and x_end of each x array are equal.
    
    y : 2xN numpy array
        Model prediction as a 2xN numpy array, where the first row represents x and the second f(x).
        y may have a different length N, than the arrays in X, and the values may be spaced at random,
        but x_0 and x_end of the final interpolation will be the intersection of the arrays in X and the array in y,
        therefore if all datapoints must be used, ensure x_0 and x_end of each array are equal.
    
    alpha : double, default=0.05
        Significance level.

    Returns
    -------
    mu_interval : 2xN numpy array
        Interval of true mean mu with (1-alpha)*100% confidence given as a 2xN numpy array [lower_boubd, upper_bound].

    E_interval : 2xN numpy array
        Interval of true error with (1-alpha)*100% confidence given as a 2xN numpy array [lower_bound, upper_bound].
    
    Notes
    -----
    Todo: Complete further, definitely add the assumptions for X and y here.


    Examples
    --------
    Todo : Complete

    """
    # 0. preproc.
    n = len(X)

    # 1. take intersection of all x arrays, such that we have the final array on which to interpolate f(x)
    # Code below doesn't do exactly what I want: say the two X vectors are [1 2 3 4] and [2 2.5 3 3.5] then I'd want a new vector [2 2.5 3 3.5], but the intersection only contains [2 3]
    # solution: find max of the minimal values, and min of the maximal values (minimal values = index 0, maximal = index -1 assuming sorted), then take union of all indexes, and finally chop off the tails
    # x_all = [x[0,:].T for x in X] # extract x
    # x_all.append(y[0,:]) # add x from y
    # x_intersect = reduce(np.intersect1d, (x_all))
    # print(x_intersect)
    # correct code below:

    x_first = [x[0,0] for x in X] # first values of X
    x_first.append(y[0,0]) # add first value of y as well
    x_last = [x[0,-1] for x in X] # last values of X
    x_last .append(y[0,-1]) # add last value of y as well
    x_first = max(x_first) # maximum of the first values
    x_last = min(x_last) # minimum of the last values.

    x_all = [x[0,:].T for x in X] # extract x
    x_all.append(y[0,:]) # add x from y
    x_union = reduce(np.union1d, (x_all))
    mask = (x_union>=x_first) &  (x_union<=x_last)
    x_final = x_union[mask] 
    # print(x_final)

    # 2. Interpolate each f(x) for these values using spline interpolation using cubic spline
    f_X_interpolated = np.empty((n, x_final.size))
    for i, x in enumerate(X):
        f = interp1d(x[0,:], x[1,:], kind='cubic')
        f_x_interpolated = f(x_final)
        f_X_interpolated[i, :] = f_x_interpolated

    f = interp1d(y[0,:], y[1,:], kind='cubic')
    f_y_interpolated = f(x_final)

    # 3. for each column of f_X_interpolated, the calculate_frequentist_metric function can now be calculated
    # mu_interval_x = np.empty((2, x_final.size))
    mu_x = np.empty((x_final.size))
    # E_interval_x = np.empty((2, x_final.size))
    E_x = np.empty((x_final.size))
    conf_interval_x = np.empty((2, x_final.size))
    for i, (col, y_x_interp) in enumerate(zip(f_X_interpolated.T, f_y_interpolated.T)):
        X_overlined, E_estimated, conf_interval = calculate_frequentist_metric(col, y_x_interp, alpha=alpha)
        # mu_interval_x[:,i] = mu_interval
        # E_interval_x[:,i] = E_interval
        conf_interval_x[:,i] = conf_interval
        mu_x[i] = X_overlined
        E_x[i] = E_estimated
        # print(mu_interval.T)
        # print(mu_interval_x)

    # Note to self: for a future version of this function it might be interesting to return the interpolation functions?
    return x_final, mu_x, E_x, conf_interval_x, f_y_interpolated

def calculate_global_frequentist_metric(X, y, alpha=0.05):
    """Calculate global frequentist metrics and return them.

    Parameters
    ----------
    X : List of 2xN numpy array
        The replicated experimental measurements. Assumed to be a list of at least two 2xN numpy arrays, in which
        the first row represents x and the second f(x). Each numpy array in the list may have a different length N,
        and the values may be spaced at random, but x_0 and x_end of the final interpolation will be the intersection
        of the various arrays in X and the single array in y, therefore if all datapoints must be used, ensure x_0 and x_end of each x array are equal.
    
    y : 2xN numpy array
        Model prediction as a 2xN numpy array, where the first row represents x and the second f(x).
        y may have a different length N, than the arrays in X, and the values may be spaced at random,
        but x_0 and x_end of the final interpolation will be the intersection of the arrays in X and the array in y,
        therefore if all datapoints must be used, ensure x_0 and x_end of each array are equal.
    
    alpha : double, default=0.05
        Significance level.

    Returns
    -------
    avg_rel_err : double
        The average relative error metric: ...
    
    avg_rel_conf_ind : double
        The average relative confidence indicator: ...
    
    max_rel_err: double
        The maximum relative error metric: ...

    Notes
    -----

    Examples
    --------

    """
    # note there is some copy paste from the other functions, so might have to revisit
    n = len(X)

    x_first = [x[0,0] for x in X] # first values of X
    x_first.append(y[0,0]) # add first value of y as well
    x_last = [x[0,-1] for x in X] # last values of X
    x_last .append(y[0,-1]) # add last value of y as well
    x_first = max(x_first) # maximum of the first values
    x_last = min(x_last) # minimum of the last values.

    x_all = [x[0,:].T for x in X] # extract x
    x_all.append(y[0,:]) # add x from y
    x_union = reduce(np.union1d, (x_all))
    mask = (x_union>=x_first) &  (x_union<=x_last)
    x_final = x_union[mask] 
    
    f_X_interpolated = np.empty((n, x_final.size))
    for i, x in enumerate(X):
        f = interp1d(x[0,:], x[1,:], kind='cubic')
        f_x_interpolated = f(x_final)
        f_X_interpolated[i, :] = f_x_interpolated

    f = interp1d(y[0,:], y[1,:], kind='cubic')
    f_y_interpolated = f(x_final)

    mu_x = np.empty((x_final.size))
    E_x = np.empty((x_final.size))
    s_x = np.empty((x_final.size))
    t_alpha_div_2_v = 0

    conf_interval_x = np.empty((2, x_final.size))
    for i, (col, y_x_interp) in enumerate(zip(f_X_interpolated.T, f_y_interpolated.T)): 
        n = col.size

        X_overlined = np.mean(col) # sample mean of X
        s = np.std(col, ddof=1) # sample standard deviation of X
        E_estimated = y_x_interp - X_overlined # estimated error
        dof = n-1 # degrees of freedom (v) for t table lookup
        t_alpha_div_2_v = stats.t.ppf(1-alpha/2, dof) # T value for 1-alpha confidence

        tmp = t_alpha_div_2_v * s/np.sqrt(n) # temporary variable to store the +/- term for the confidence interval
        conf_interval = np.array([-tmp, tmp]) # double sided confidence interval on experimental data.

        conf_interval_x[:,i] = conf_interval
        mu_x[i] = X_overlined
        E_x[i] = E_estimated
        s_x[i] = s

    # exclude from calculation all points where mu_x is 0. Otherwise might get
    # NaN.

    bool_idx = np.isin(mu_x, 0)
    excl_idx = (np.where(bool_idx == True))[0]
    if len(excl_idx)>0:
        # best to print the warning and exclude those indexes from being used in the calculation of the metric.
        # since simulations often all start at 0 the first index will often have std = 0
        warnings.warn("Mean is 0 at indexes" + str(excl_idx) + ", ignoring them in calculation, otherwise metrics yield infinite")
    inv_bool_idx = np.logical_not(bool_idx)
    
    mu_x = mu_x[inv_bool_idx]
    x_final = x_final[inv_bool_idx]
    E_x = E_x[inv_bool_idx]
    s_x = s_x[inv_bool_idx]

    # actual new calculations
    avg_rel_err = 1/(x_final[-1] - x_final[0]) * np.trapz(np.abs((E_x)/mu_x), x_final)

    avg_rel_conf_ind = t_alpha_div_2_v/((x_final[-1] - x_final[0])*np.sqrt(n)) * np.trapz(np.abs(s_x/mu_x), x_final)

    max_rel_err = np.max(np.abs((E_x)/mu_x))

    return avg_rel_err, avg_rel_conf_ind, max_rel_err
    



        