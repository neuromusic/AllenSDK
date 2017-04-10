from .eventdetection import detect_events
from statsmodels.sandbox.stats.multicomp import multipletests
import numpy as np
from .utilities import get_A, get_A_blur, get_shuffle_matrix, get_components

# import h5py

# from receptivefield.tools import dict_generator

# from receptivefield.core.eventdetection import detect_events

# from receptivefield.core.utilities import plot_fields, get_A, get_A_blur, get_components
# from receptivefield.core.postprocessing import run_postprocessing

def events_to_pvalues_no_fdr_correction(data, event_vector, number_of_shuffles=5000, response_detection_error_std_dev=.1, seed=1, debug=False):

    # Load design matrix and event vector
    A = get_A_blur(data, debug=debug)

    # Initializations:
    number_of_events = event_vector.sum()
    np.random.seed(seed)

    shuffle_data = get_shuffle_matrix(data, number_of_events, number_of_shuffles=number_of_shuffles, response_detection_error_std_dev=response_detection_error_std_dev, debug=debug)

    # Build list of p-values:
    response_triggered_stimulus_vector = A.dot(event_vector)/number_of_events
    p_value_list = []
    for pi in range(2*16*28):
        curr_p_value = 1-(shuffle_data[pi, :] < response_triggered_stimulus_vector[pi]).sum()*1./number_of_shuffles
        p_value_list.append(curr_p_value)

    return np.array(p_value_list)

def run_receptive_field_computation(data, csid, **kwargs):

    alpha = kwargs.pop('alpha')

    event_vector = detect_events(data, csid)

    print 'number_of_events', event_vector.sum()
    pvalues = events_to_pvalues_no_fdr_correction(data, event_vector, **kwargs)
    pvalues_on, pvalues_off = pvalues[:16*28].reshape(16, 28), pvalues[16*28:].reshape(16, 28)

    fdr_corrected_pvalues = multipletests(pvalues, alpha=alpha)[1]

    fdr_corrected_pvalues_on = fdr_corrected_pvalues[:16 * 28].reshape(16, 28)
    _fdr_mask_on = np.zeros_like(pvalues_on, dtype=np.bool)
    _fdr_mask_on[fdr_corrected_pvalues_on < alpha] = True
    components_on, number_of_components_on = get_components(_fdr_mask_on)

    fdr_corrected_pvalues_off = fdr_corrected_pvalues[16 * 28:].reshape(16, 28)
    _fdr_mask_off = np.zeros_like(pvalues_off, dtype=np.bool)
    _fdr_mask_off[fdr_corrected_pvalues_off < alpha] = True
    components_off, number_of_components_off = get_components(_fdr_mask_off)

    A = get_A(data)
    A_blur = get_A_blur(data)

    response_triggered_stimulus_field = A.dot(event_vector)
    response_triggered_stimulus_field_on = response_triggered_stimulus_field[:16*28].reshape(16, 28)
    response_triggered_stimulus_field_off = response_triggered_stimulus_field[16 * 28:].reshape(16, 28)

    response_triggered_stimulus_field_convolution = A_blur.dot(event_vector)
    response_triggered_stimulus_field_convolution_on = response_triggered_stimulus_field_convolution[:16*28].reshape(16, 28)
    response_triggered_stimulus_field_convolution_off = response_triggered_stimulus_field_convolution[16 * 28:].reshape(16, 28)

    on_dict = {'pvalues':{'data':pvalues_on},
               'fdr_corrected':{'data':fdr_corrected_pvalues_on, 'attrs':{'alpha':alpha, 'min_p':fdr_corrected_pvalues_on.min()}},
               'fdr_mask': {'data':components_on, 'attrs':{'alpha':alpha, 'number_of_components':number_of_components_on, 'number_of_pixels':components_on.sum(axis=1).sum(axis=1)}},
               'rts_convolution':{'data':response_triggered_stimulus_field_convolution_on},
               'rts': {'data': response_triggered_stimulus_field_on}
               }
    off_dict = {'pvalues':{'data':pvalues_off},
               'fdr_corrected':{'data':fdr_corrected_pvalues_off, 'attrs':{'alpha':alpha, 'min_p':fdr_corrected_pvalues_off.min()}},
               'fdr_mask': {'data':components_off, 'attrs':{'alpha':alpha, 'number_of_components':number_of_components_off, 'number_of_pixels':components_off.sum(axis=1).sum(axis=1)}},
               'rts_convolution': {'data': response_triggered_stimulus_field_convolution_off},
               'rts': {'data': response_triggered_stimulus_field_off}
                }

    result_dict = {'event_vector': {'data':event_vector, 'attrs':{'number_of_events':event_vector.sum()}},
                   'on':on_dict,
                   'off':off_dict,
                   'attrs':{'csid':csid}}

    return result_dict

def get_receptive_field_data_dict_with_postprocessing(data, csid, **kwargs):

    receptive_field_data_dict = run_receptive_field_computation(data, csid, **kwargs)
    receptive_field_data_dict = run_postprocessing(receptive_field_data_dict)

    return receptive_field_data_dict

def get_attribute_dict(receptive_field_data_dict):

    attribute_dict = {}
    for x in dict_generator(receptive_field_data_dict):
        if x[-3] == 'attrs':
            if len(x[:-3]) == 0:
                key = x[-2]
            else:
                key = '/'.join(['/'.join(x[:-3]), x[-2]])
            attribute_dict[key] = x[-1]

    return attribute_dict


def print_summary(receptive_field_data_dict):
    for key_val in sorted(get_attribute_dict(receptive_field_data_dict).iteritems(), key=lambda x:x[0]):
        print "%s : %s" % key_val

def write_receptive_field_data_dict_to_h5(receptive_field_data_dict, file_name, prefix=''):

    attr_list = []
    f = h5py.File(file_name, 'a')
    for x in dict_generator(receptive_field_data_dict):

        if x[-2] == 'data':
            f['/'.join([prefix]+x[:-1])] = x[-1]
        elif x[-3] == 'attrs':
            attr_list.append(x)
        else:
            raise Exception

    for x in attr_list:
        if len(x) > 3:
            f['/'.join([prefix]+x[:-3])].attrs[x[-2]] = x[-1]
        else:
            assert len(x) == 3
            if prefix == '':

                if x[-1] is None:
                    f.attrs[x[-2]] = np.NaN
                else:
                    f.attrs[x[-2]] = x[-1]
            else:
                if x[-1] is None:
                    f[prefix].attrs[x[-2]] = np.NaN
                else:
                    f[prefix].attrs[x[-2]] = x[-1]

    f.close()

def read_h5_group(g):
    return_dict = {}
    if len(g.attrs) > 0:
        return_dict['attrs'] = dict(g.attrs)
    for key in g:
        if key == 'data':
            return_dict[key] = g[key].value
        else:
            return_dict[key] = read_h5_group(g[key])

    return return_dict

def read_receptive_field_data_dict_from_h5(file_name, path=None):

    f = h5py.File(file_name, 'r')
    if path is None:
        receptive_field_data_dict = read_h5_group(f)
    else:
        receptive_field_data_dict = read_h5_group(f[path])
    f.close()

    return receptive_field_data_dict


# if __name__ == "__main__":
#
#     from utilities import plot_fields
#     from receptivefield.tools import get_temp_file_name
#     from receptivefield.core.visualization import plot_receptive_field_data
#
#     csid = 539919364
#     # csid = 539772953
#     # csid = 541095385
#     # csid = 517503985 #horizontal on
#     # csid = 517472007    # debug correction chi square
#     # csid = 540988186
#     # csid = 517526760
#     # csid = 517472524 # Called false
#     # csid = 517504484
#
#     # receptive_field_data_dict = get_receptive_field_data_dict_with_postprocessing(csid, debug=True, alpha=.05)
#     receptive_field_data_dict = get_receptive_field_data_dict_with_postprocessing(csid=csid, alpha=.05, debug=True)
#
#     # write_receptive_field_data_dict_to_h5(receptive_field_data_dict, 'tmp.h5', prefix=str(csid))
#     # receptive_field_data_dict = read_receptive_field_data_dict_from_h5('tmp.h5', path=str(csid))
#     print_summary(receptive_field_data_dict)
#     plot_receptive_field_data(receptive_field_data_dict)
#
#
#
#
#     # print_summary(receptive_field_data_dict)
    # plot_receptive_field_data(receptive_field_data_dict)



    # write_receptive_field_data_dict_to_h5(receptive_field_data_dict, get_temp_file_name(), prefix=str(csid))


    # receptive_field_data_dict = run_receptive_field_computation(csid=csid, alpha=.05, debug=False)

