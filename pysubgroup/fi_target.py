'''
Created on 29.09.2017

@author: lemmerfn
'''
from collections import namedtuple
from functools import total_ordering
import numpy as np
import pysubgroup as ps



@total_ordering
class FITarget():
    def __repr__(self):
        return "T: Frequent Itemsets"

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __lt__(self, other):
        return str(self) < str(other)

    def get_attributes(self):
        return []

    def get_base_statistics(self, data, subgroup, weighting_attribute=None):
        if weighting_attribute is None:
            sg_instances = subgroup.covers(data)
            return sg_instances.sum()
        else:
            raise NotImplementedError("Attribute weights with numeric targets are not yet implemented.")

    def calculate_statistics(self, subgroup, data, weighting_attribute=None):
        if weighting_attribute is not None:
            raise NotImplementedError("Attribute weights with numeric targets are not yet implemented.")
        sg_instances = subgroup.covers(data)

        subgroup.statistics['size_sg'] = len(sg_instances)
        subgroup.statistics['size_dataset'] = len(data)


class SimpleCountQF(ps.AbstractInterestingnessMeasure):
    tpl = namedtuple('CountQF_parameters', ('subgroup_size'))

    def __init__(self):
        self.required_stat_attrs = ('subgroup_size',)
        self.has_constant_statistics = True

    def calculate_constant_statistics(self, task):
        pass

    def calculate_statistics(self, subgroup, data=None):
        if hasattr(subgroup, "representation"):
            cover_arr = subgroup
        elif isinstance(subgroup, slice):
            cover_arr = subgroup
        else:
            cover_arr = subgroup.covers(data)
        return SimpleCountQF.tpl(np.count_nonzero(cover_arr))

    def gp_get_stats(self, _):
        return {"subgroup_size" : 1}

    def gp_get_null_vector(self):
        return {"subgroup_size":0}

    def gp_merge(self, l, r):
        l["subgroup_size"] += r["subgroup_size"]

    def gp_get_params(self, _cover_arr, v):
        return SimpleCountQF.tpl(v['subgroup_size'])

    def gp_to_str(self, stats):
        return str(stats['subgroup_size'])

    @property
    def gp_requires_cover_arr(self):
        return False


class CountQF(SimpleCountQF, ps.BoundedInterestingnessMeasure):
    def evaluate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        return statistics.subgroup_size

    def optimistic_estimate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        return statistics.subgroup_size

    def is_applicable(self, subgroup):
        return isinstance(subgroup.target, FITarget)

    def supports_weights(self):
        return False




class AreaQF(SimpleCountQF):
    def evaluate(self, subgroup, statistics=None):
        statistics = self.ensure_statistics(subgroup, statistics)
        return statistics.subgroup_size * subgroup.depth

    def is_applicable(self, subgroup):
        return isinstance(subgroup.target, FITarget)

    def supports_weights(self):
        return False
