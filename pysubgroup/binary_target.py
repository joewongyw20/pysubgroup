'''
Created on 29.09.2017

@author: lemmerfn
'''
from collections import namedtuple
from functools import total_ordering
import numpy as np
import scipy.stats

import pysubgroup as ps

from pysubgroup.subgroup import EqualitySelector


@total_ordering
class BinaryTarget():

    def __init__(self, target_attribute=None, target_value=None, target_selector=None):
        """
        Creates a new target for the boolean model class (classic subgroup discovery).
        If target_attribute and target_value are given, the target_selector is computed using attribute and value
        """
        if target_attribute is not None and target_value is not None:
            if target_selector is not None:
                raise BaseException("BinaryTarget is to be constructed EITHER by a selector OR by attribute/value pair")
            target_selector = EqualitySelector(target_attribute, target_value)
        if target_selector is None:
            raise BaseException("No target selector given")
        self.target_selector = target_selector

    def __repr__(self):
        return "T: " + str(self.target_selector)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __lt__(self, other):
        return str(self) < str(other)

    def covers(self, instance):
        return self.target_selector.covers(instance)

    def get_attributes(self):
        return [self.target_selector.get_attribute_name()]

    def get_base_statistics(self, subgroup, data):

        sg_instances = subgroup.covers(data)
        positives = self.covers(data)
        instances_subgroup = np.sum(sg_instances)
        positives_dataset = np.sum(positives)
        instances_dataset = len(data)
        positives_subgroup = np.sum(np.logical_and(sg_instances, positives))
        return instances_dataset, positives_dataset, instances_subgroup, positives_subgroup


    def calculate_statistics(self, subgroup, data):
        (instances_dataset, positives_dataset, instances_subgroup, positives_subgroup) = \
            self.get_base_statistics(subgroup, data)
        statistics = {}
        statistics['size_sg'] = instances_subgroup
        statistics['size_dataset'] = instances_dataset
        statistics['positives_sg'] = positives_subgroup
        statistics['positives_dataset'] = positives_dataset
        statistics['size_complement'] = instances_dataset - instances_subgroup
        statistics['relative_size_sg'] = instances_subgroup / instances_dataset
        statistics['relative_size_complement'] = (instances_dataset - instances_subgroup) / instances_dataset
        statistics['coverage_sg'] = positives_subgroup / positives_dataset
        statistics['coverage_complement'] = (positives_dataset - positives_subgroup) / positives_dataset
        statistics['target_share_sg'] = positives_subgroup / instances_subgroup
        statistics['target_share_complement'] = (positives_dataset - positives_subgroup) / (instances_dataset - instances_subgroup)
        statistics['target_share_dataset'] = positives_dataset / instances_dataset
        statistics['lift'] = (positives_subgroup / instances_subgroup) / (positives_dataset / instances_dataset)
        return statistics



class SimplePositivesQF(ps.AbstractInterestingnessMeasure): # pylint: disable=abstract-method
    tpl = namedtuple('PositivesQF_parameters', ('size', 'positives_count'))

    def __init__(self):
        self.datatset_statistics = None
        self.positives = None
        self.has_constant_statistics = False
        self.required_stat_attrs = ('size', 'positives_count')

    def calculate_constant_statistics(self, task):
        assert isinstance(task.target, BinaryTarget)
        data = task.data
        self.positives = task.target.covers(data)
        self.datatset_statistics = SimplePositivesQF.tpl(len(data), np.sum(self.positives))
        self.has_constant_statistics = True

    def calculate_statistics(self, subgroup, data=None):
        if hasattr(subgroup, "representation"):
            cover_arr = subgroup
            size = subgroup.size
        elif isinstance(subgroup, slice):
            cover_arr = subgroup
            # https://stackoverflow.com/questions/36188429/retrieve-length-of-slice-from-slice-object-in-python
            size = len(range(*subgroup.indices(len(self.positives))))
        else:
            cover_arr = subgroup.covers(data)
            size = np.count_nonzero(cover_arr)
        return SimplePositivesQF.tpl(size, np.count_nonzero(self.positives[cover_arr]))

    def is_applicable(self, subgroup):
        return isinstance(subgroup.target, BinaryTarget)



# TODO Make ChiSquared useful for real nominal data not just binary
# TODO Introduce Enum for direction
# TODO Maybe it is possible to give a optimistic estimate for ChiSquared
class ChiSquaredQF(SimplePositivesQF):
    """
    ChiSquaredQF which test for statistical independence of a subgroup against it's complement

    ...

    """

    @staticmethod
    def chi_squared_qf(instances_dataset, positives_dataset, instances_subgroup, positives_subgroup, min_instances=5, bidirect=True, direction_positive=True, index=0):
        """
        Performs chi2 test of statistical independence

        Test whether a subgroup is statistically independent from it's complement (see scipy.stats.chi2_contingency).


        Parameters
        ----------
        instances_dataset, positives_dataset, instances_subgroup, positives_subgroup : int
            counts of subgroup and dataset
        min_instances : int, optional
            number of required instances, if less -inf is returned for that subgroup
        bidirect : bool, optional
            If true both directions are considered interesting else direction_positive decides which direction is interesting
        direction_positive: bool, optional
            Only used if bidirect=False; specifies whether you are interested in positive (True) or negative deviations
        index : {0, 1}, optional
            decides whether the test statistic (0) or the p-value (1) should be used
        """

        if (instances_subgroup < min_instances) or ((instances_dataset - instances_subgroup) < min_instances):
            return float("-inf")

        negatives_subgroup =  instances_subgroup - positives_subgroup # pylint: disable=bad-whitespace
        negatives_dataset =    instances_dataset - positives_dataset # pylint: disable=bad-whitespace
        negatives_complement = negatives_dataset - negatives_subgroup
        positives_complement = positives_dataset - positives_subgroup

        val = scipy.stats.chi2_contingency([[positives_subgroup, positives_complement],
                                            [negatives_subgroup, negatives_complement]], correction=False)[index]
        if bidirect:
            return val
        p_subgroup = positives_subgroup / instances_subgroup
        p_dataset = positives_dataset / instances_dataset
        if direction_positive and p_subgroup > p_dataset:
            return val
        elif not direction_positive and p_subgroup < p_dataset:
            return val
        return -val

    @staticmethod
    def chi_squared_qf_weighted(subgroup, data, weighting_attribute, effective_sample_size=0, min_instances=5, ):
        (instancesDataset, positivesDataset, instancesSubgroup, positivesSubgroup) = subgroup.get_base_statistics(data, weighting_attribute)
        if (instancesSubgroup < min_instances) or ((instancesDataset - instancesSubgroup) < 5):
            return float("inf")
        if effective_sample_size == 0:
            effective_sample_size = ps.effective_sample_size(data[weighting_attribute])
        # p_subgroup = positivesSubgroup / instancesSubgroup
        # p_dataset = positivesDataset / instancesDataset

        negatives_subgroup = instancesSubgroup - positivesSubgroup
        negatives_dataset = instancesDataset - positivesDataset
        positives_complement = positivesDataset - positivesSubgroup
        negatives_complement = negatives_dataset - negatives_subgroup
        val = scipy.stats.chi2_contingency([[positivesSubgroup, positives_complement],
                                            [negatives_subgroup, negatives_complement]], correction=True)[0]
        return scipy.stats.chi2.sf(val * effective_sample_size / instancesDataset, 1)

    def __init__(self, direction='both', min_instances=5, stat='chi2'):
        """
        Parameters
        ----------
        direction : {'both', 'positive', 'negative'}
            direction of deviation that is of interest
        min_instances : int, optional
            number of required instances, if less -inf is returned for that subgroup
        stat : {'chi2', 'p'}
            whether to report the test statistic or the p-value (see scipy.stats.chi2_contingency)
        """

        if direction == 'both':
            self.bidirect = True
            self.direction_positive = True
        if direction == 'positive':
            self.bidirect = False
            self.direction_positive = True
        if direction == 'negative':
            self.bidirect = False
            self.direction_positive = False
        self.min_instances = min_instances
        self.index = {'chi2' : 0, 'p': 1}[stat]
        super().__init__()


    def evaluate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        datatset = self.datatset_statistics
        return ChiSquaredQF.chi_squared_qf(datatset.size, datatset.positives_count, statistics.size, statistics.positives_count, self.min_instances, self.bidirect, self.direction_positive, self.index)

    def supports_weights(self):
        return True




class StandardQF(SimplePositivesQF, ps.BoundedInterestingnessMeasure):
    """
    StandardQF which weights the relative size against the difference in averages

    The StandardQF is a general form of quality function which for different values of a is order equivalen to
    many popular quality measures.

    Attributes
    ----------
    a : float
        used as an exponent to scale the relative size to the difference in averages

    """

    @staticmethod
    def standard_qf(a, instances_dataset, positives_dataset, instances_subgroup, positives_subgroup):
        if not hasattr(instances_subgroup, '__array_interface__') and (instances_subgroup == 0):
            return np.nan
        p_subgroup = np.divide(positives_subgroup, instances_subgroup)
        #if instances_subgroup == 0:
        #    return 0
        #p_subgroup = positives_subgroup / instances_subgroup
        p_dataset = positives_dataset / instances_dataset
        return (instances_subgroup / instances_dataset) ** a * (p_subgroup - p_dataset)

    def __init__(self, a):
        """
        Parameters
        ----------
        a : float
            exponent to scale the relative size to the difference in means
        """

        self.a = a
        super().__init__()

    def evaluate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        datatset = self.datatset_statistics
        return StandardQF.standard_qf(self.a, datatset.size, datatset.positives_count, statistics.size, statistics.positives_count)

    def optimistic_estimate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        datatset = self.datatset_statistics
        return StandardQF.standard_qf(self.a, datatset.size, datatset.positives_count, statistics.positives_count, statistics.positives_count)

    def optimistic_generalisation(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        datatset = self.datatset_statistics
        pos_remaining = datatset.positives_count - statistics.positives_count
        return StandardQF.standard_qf(self.a, datatset.size, datatset.positives_count, statistics.size + pos_remaining, datatset.positives_count)

    def supports_weights(self):
        return True




class LiftQF(StandardQF):
    """
    Lift Quality Function

    LiftQF is a StandardQF with a=0.
    Thus it treats the difference in ratios as the quality without caring about the relative size of a subgroup.
    """

    def __init__(self):
        """
        """

        super().__init__(0.0)



# TODO add true binomial quality function as in https://opus.bibliothek.uni-wuerzburg.de/opus4-wuerzburg/frontdoor/index/index/docId/1786
class SimpleBinomialQF(StandardQF):
    """
    Simple Binomial Quality Function

    SimpleBinomialQF is a StandardQF with a=0.5.
    It is an order equivalent approximation of the full binomial test if the subgroup size is much smaller than the size of the entire dataset.
    """

    def __init__(self):
        """
        """

        super().__init__(0.5)



class WRAccQF(StandardQF):
    """
    Weighted Relative Accuracy Quality Function

    WRAccQF is a StandardQF with a=1.
    It is order equivalent to the difference in the observed and expected number of positive instances.
    """

    def __init__(self):
        """
        """

        super().__init__(1.0)




#####
# GeneralizationAware Interestingness Measures
#####
class GeneralizationAware_StandardQF(ps.GeneralizationAwareQF_stats):
    def __init__(self, a):
        super().__init__(StandardQF(0))
        self.a = a


    def get_max(self, *args):
        max_ratio = 0.0
        max_stats = None
        for stat in args:
            if stat.size > 0:
                ratio = stat.positives_count / stat.size
                if ratio > max_ratio:
                    max_ratio = ratio
                    max_stats = stat
        return max_stats

    def evaluate(self, subgroup, statistics_or_data=None):
        statistics = self.ensure_statistics(subgroup, statistics_or_data)
        sg_stats = statistics.subgroup_stats
        general_stats = statistics.generalisation_stats
        if sg_stats.size == 0 or general_stats.size == 0:
            return np.nan

        sg_ratio = sg_stats.positives_count / sg_stats.size
        general_ratio = general_stats.positives_count / general_stats.size
        return (sg_stats.size / self.stats0.size) ** self.a * (sg_ratio - general_ratio)
