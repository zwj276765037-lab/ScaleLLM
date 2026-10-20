"""Disjoint endpoint-demand categories; these are not actual-route classes."""
import collections
import csv
import json


def add_classification(out, plan, nets, failed, cells, sites, groups):
    classes = collections.defaultdict(list)
    module_classes = collections.Counter()
    type_combinations = collections.Counter()
    boundary_subtypes = collections.Counter()
    for net in failed:
        known = {'SLR0', 'SLR1', 'SLR2'}
        source = net['source_SLR']
        loads = set(net['load_SLRs'])
        if (net['bucket'] != 'SINGLE_DRIVER' or source not in known
                or not loads or not loads <= known or net['unknown']):
            category = 'UNKNOWN_ENDPOINT_DEMAND'
        else:
            all_slrs = loads | {source}
            if {'SLR0', 'SLR2'} <= all_slrs:
                category = 'TWO_BOUNDARY_ENDPOINT_DEMAND'
                boundary_subtypes['SOURCE1_MULTICAST_TO_0_AND_2' if source == 'SLR1'
                                  else 'DIRECT_SOURCE_LOAD_0_TO_2'] += 1
            elif len(all_slrs) > 1:
                category = 'ADJACENT_ENDPOINT_DEMAND'
            else:
                category = 'LOCAL_ENDPOINTS'
        net['endpoint_class'] = category
        classes[category].append(net['canonical'])
        module_classes[category, net['driver_module']] += 1
        type_combinations[','.join(net['types'])] += 1
    denominator = len(failed)
    with (out / 'endpoint_class_counts.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['endpoint_class', 'canonical_conflict_nets',
                         'canonical_denominator', 'fraction', 'actual_route_containment'])
        for category in ('LOCAL_ENDPOINTS', 'ADJACENT_ENDPOINT_DEMAND',
                         'TWO_BOUNDARY_ENDPOINT_DEMAND', 'UNKNOWN_ENDPOINT_DEMAND'):
            count = len(classes[category])
            writer.writerow([category, count, denominator,
                             count / denominator if denominator else None, 'NOT_IMPLIED'])
    with (out / 'endpoint_class_modules.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['endpoint_class', 'actual_driver_module', 'canonical_conflict_nets'])
        for (category, module), count in sorted(module_classes.items(), key=lambda x: (-x[1], x[0])):
            writer.writerow([category, module, count])
    with (out / 'exclusive_type_combinations.tsv').open('w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['native_type_combination', 'canonical_conflict_nets'])
        writer.writerows(sorted(type_combinations.items(), key=lambda x: (-x[1], x[0])))
    (out / 'endpoint_class_coverage.json').write_text(json.dumps({
        'canonical_denominator': denominator,
        'class_sum': sum(map(len, classes.values())),
        'mutually_exclusive': True,
        'rule': plan['endpoint_class_rule'],
        'not_actual_route_containment': True,
        'native_report_conflict_nets': plan['native_report_conflict_nets'],
        'canonical_minus_native_report': denominator - plan['native_report_conflict_nets'],
        'constants_retained': True,
        'two_boundary_subtypes': dict(boundary_subtypes),
        'unmeasured': ['all_conflict_actual_route_SLRs', 'all_797175_overlap_node_membership']
    }, indent=2) + '\n')
    selected = set()
    for category in sorted(classes):
        eligible = [name for name in sorted(classes[category])
                    if len(nets[name]['loads']) <= plan['deep_max_load_pins']]
        selected.update(eligible[:plan['cross_class_representatives']])
    return selected
