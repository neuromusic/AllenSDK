from .utilities import smooth
import numpy as np
import scipy.stats as sps

def detect_events_cache(csid):
    return detect_events(csid)

def detect_events(data, csid):

    stimulus_table = data.get_stimulus_table('locally_sparse_noise')
    cell_index = data.get_cell_specimen_indices(cell_specimen_ids=[csid])[0]
    dff_trace = data.get_dff_traces()[1][cell_index, :]

    k_min = 0
    k_max = 10
    delta = 3

    dff_trace = smooth(dff_trace, 5)

    var_dict = {}
    for ii, fi in enumerate(stimulus_table['start'].values):

        if ii > 0 and stimulus_table.iloc[ii].start == stimulus_table.iloc[ii-1].end:
            offset = 1
        else:
            offset = 0

        if fi + k_min >= 0 and fi + k_max <= len(dff_trace):
            trace = dff_trace[fi + k_min+1+offset:fi + k_max+1+offset]

            xx = (trace - trace[0])[delta] - (trace - trace[0])[0]
            yy = max((trace - trace[0])[delta + 2] - (trace - trace[0])[0 + 2],
                     (trace - trace[0])[delta + 3] - (trace - trace[0])[0 + 3],
                     (trace - trace[0])[delta + 4] - (trace - trace[0])[0 + 4])

            var_dict[ii] = (trace[0], trace[-1], xx, yy)

    xx_list, yy_list = [], []
    for _, _, xx, yy in var_dict.itervalues():
        xx_list.append(xx)
        yy_list.append(yy)

    mu_x = np.median(xx_list)
    mu_y = np.median(yy_list)

    xx_centered = np.array(xx_list)-mu_x
    yy_centered = np.array(yy_list)-mu_y

    std_factor = 1
    std_x = 1./std_factor*np.percentile(np.abs(xx_centered), [100*(1-2*(1-sps.norm.cdf(std_factor)))])
    std_y = 1./std_factor*np.percentile(np.abs(yy_centered), [100*(1-2*(1-sps.norm.cdf(std_factor)))])

    curr_inds = []
    allowed_sigma = 4
    for ii, (xi, yi) in enumerate(zip(xx_centered, yy_centered)):
        if np.sqrt(((xi)/std_x)**2+((yi)/std_y)**2) < allowed_sigma:
            curr_inds.append(True)
        else:
            curr_inds.append(False)

    curr_inds = np.array(curr_inds)
    data_x = xx_centered[curr_inds]
    data_y = yy_centered[curr_inds]
    Cov = np.cov(data_x, data_y)
    Cov_Factor = np.linalg.cholesky(Cov)
    Cov_Factor_Inv = np.linalg.inv(Cov_Factor)

    #===================================================================================================================

    noise_threshold = max(allowed_sigma * std_x + mu_x, allowed_sigma * std_y + mu_y)
    mu_array = np.array([mu_x, mu_y])
    yes_set, no_set = set(), set()
    for ii, (t0, tf, xx, yy) in var_dict.iteritems():


        xi_z, yi_z = Cov_Factor_Inv.dot((np.array([xx,yy]) - mu_array))

        # Conditions in order:
        # 1) Outside noise blob
        # 2) Minimum change in df/f
        # 3) Change evoked by this trial, not previous
        # 4) At end of trace, ended up outside of noise floor

        if np.sqrt(xi_z**2 + yi_z**2) > 4 and yy > .05 and xx < yy and tf > noise_threshold/2:
            yes_set.add(ii)
        else:
            no_set.add(ii)

    assert len(var_dict) == 8880
    b = np.zeros(8880, dtype=np.bool)
    for yi in yes_set:
        b[yi] = True

    return b

if __name__ == "__main__":

    csid = 541095385
    b = detect_events(csid)
    assert b.sum() == 423 # 422 by old method


    csid = 540988186
    b = detect_events_cache(csid)
    assert b.sum() == 113 # 113 by old method