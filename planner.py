import collections
import json
import sys
from operator import itemgetter
from typing import List, Tuple

from ortools.sat.python import cp_model

Recipe = collections.namedtuple('Recipe', 'duration demands resources')
Resource = collections.namedtuple('Resource', 'name capacity')
Task = collections.namedtuple('Task', 'name recipes successors')


def _as_duration(n: int) -> str:
    return f'{n // 60:>02d}h{n % 60:>02d}m'


def _as_time(n: int) -> str:
    return f'{n // 60:>02d}:{n % 60:>02d}'


def _flatten(ts: collections.abc.Mapping, pk=''):
    items = []
    for k, v in ts.items():
        new_key = f'{pk}.{k}' if pk else k
        if isinstance(v, collections.abc.Mapping) and 'recipes' not in v.keys():
            items.extend(dict(_flatten(v, new_key)).items())
        else:
            items.append((new_key, v))
    return items


def _transform(ts: dict, rs: List[Tuple[str, int]]) -> Tuple[List[Task], List[Resource]]:
    resource_map = {res: i for i, [res, _] in enumerate(rs)}
    ts = _flatten(ts)
    return (
        [Task(
            k,
            [Recipe(
                r['duration'],
                *(list(zip(*[(n, resource_map[rr]) for (n, rr) in r.get('demands', [])])) or ([tuple()] * 2))
            ) for r in data.get('recipes', [])],
            [next((i, delay) for i, (kk, _) in enumerate(ts) if kk == s) for [s, delay] in data.get('successors', [])]
        ) for i, (k, data) in enumerate(ts)],
        [Resource(*r) for r in rs]
    )


def solveRCPSP(tasks: List[Task], resources: List[Resource], params={}):
    model = cp_model.CpModel()

    horizon = sum(max(r.duration for r in t.recipes) + sum(d for [_, d] in t.successors if d >= 0) for t in tasks)
    task_durations = {}
    task_ends = {}
    task_indices = range(len(tasks))
    task_intervals = {}
    task_resource_to_fixed_demands = collections.defaultdict(dict)
    task_starts = {}
    task_to_resource_demands = collections.defaultdict(list)
    task_to_presence_literals = collections.defaultdict(list)
    task_to_recipe_durations = collections.defaultdict(list)
    resource_indices = range(len(resources))
    resource_to_sum_of_demand_max = collections.defaultdict(int)

    for t in task_indices:
        task = tasks[t]
        recipe_indices = range(len(task.recipes))

        start_var = model.NewIntVar(0, horizon, f'start_of_task_{t}')
        end_var = model.NewIntVar(0, horizon, f'end_of_task_{t}')

        literals = [model.NewBoolVar(f'is_present_{t}_{r}') for r in recipe_indices]
        model.Add(cp_model.LinearExpr.Sum(literals) == 1)

        demand_matrix = collections.defaultdict(int)

        for recipe_index, recipe in enumerate(task.recipes):
            task_to_recipe_durations[t].append(recipe.duration)
            for demand, resource in zip(recipe.demands, recipe.resources):
                demand_matrix[(resource, recipe_index)] = demand

        duration_var = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(task_to_recipe_durations[t]),
            f'duration_of_task_{t}'
        )

        min_duration = min(task_to_recipe_durations[t])
        shifted = [x - min_duration for x in task_to_recipe_durations[t]]
        model.Add(duration_var == min_duration + cp_model.LinearExpr.ScalProd(literals, shifted))

        task_interval = model.NewIntervalVar(start_var, duration_var, end_var, f'task_interval_{t}')

        task_starts[t] = start_var
        task_ends[t] = end_var
        task_durations[t] = duration_var
        task_intervals[t] = task_interval
        task_to_presence_literals[t] = literals

        for resource in resource_indices:
            demands = [demand_matrix[(resource, recipe)] for recipe in recipe_indices]
            task_resource_to_fixed_demands[(t, resource)] = demands
            demand_var = model.NewIntVarFromDomain(cp_model.Domain.FromValues(demands), f'demand_{t}_{resource}')
            task_to_resource_demands[t].append(demand_var)

            min_demand = min(demands)
            shifted = [x - min_demand for x in demands]
            model.Add(demand_var == min_demand + cp_model.LinearExpr.ScalProd(literals, shifted))
            resource_to_sum_of_demand_max[resource] += max(demands)

    makespan = model.NewIntVar(0, horizon, 'makespan')
    makespan_size = model.NewIntVar(1, horizon, 'interval_makespan_size')
    interval_makespan = model.NewIntervalVar(
        makespan,
        makespan_size,
        model.NewConstant(horizon + 1),
        'interval_makespan'
    )

    for t in task_indices:
        for [s, delay] in tasks[t].successors:
            if delay > 0:
                model.Add(task_starts[s] - task_ends[t] <= delay)
            model.Add(task_ends[t] <= task_starts[s])
        else:
            if len(tasks[t].successors) == 0:
                model.Add(task_ends[t] <= makespan)

    for r in resource_indices:
        resource = resources[r]
        c = resource.capacity
        if c < 0:
            c = resource_to_sum_of_demand_max[r]

        intervals = [task_intervals[t] for t in task_indices]
        demands = [task_to_resource_demands[t][r] for t in task_indices]

        energies = []
        for t in task_indices:
            literals = task_to_presence_literals[t]
            fixed_energies = [
                task_resource_to_fixed_demands[(t, r)][index] * task_to_recipe_durations[t][index]
                for index in range(len(literals))
            ]
            min_energy = min(fixed_energies)
            scaled_energies = [x - min_energy for x in fixed_energies]
            energies.append(min_energy + cp_model.LinearExpr.ScalProd(literals, scaled_energies))

        intervals.append(interval_makespan)
        demands.append(c)
        energies.append(c * makespan_size)
        model.AddCumulativeWithEnergy(intervals, demands, energies, c)

    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    # solver.parameters.log_search_progress = True
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(
            'Optimal' if status == cp_model.OPTIMAL else 'Feasible',
            'schedule will take',
            _as_duration(int(solver.ObjectiveValue()))
        )

        if 'start' in params:
            offset = int((start := params['start'].split(':'))[0]) * 60 + int(start[1])
            print(f'If you start cooking at {params["start"]}, then dinner can be served by {_as_time(offset + int(solver.ObjectiveValue()))}')
        elif 'dinner' in params:
            offset = (int((dinner := params['dinner'].split(':'))[0]) * 60 + int(dinner[1])) - int(solver.ObjectiveValue())
            print('Start cooking at', _as_time(offset), 'if dinner is to be served by', params['dinner'])
        else:
            offset = 0

        print()

        longest_task_name = max([len(t.name) for t in tasks])
        for t in sorted(task_indices, key=lambda i: solver.Value(task_starts[i])):
            r = next(i for i, r in enumerate(tasks[t].recipes) if solver.BooleanValue(task_to_presence_literals[t][i]))
            print(
                f'{tasks[t].name:>{longest_task_name}}',
                '::',
                _as_time(solver.Value(task_starts[t]) + offset),
                '-',
                _as_time(solver.Value(task_ends[t]) + offset),
                *([
                      'using',
                      f'[{", ".join([resources[i].name for i in tasks[t].recipes[r].resources])}]'
                  ] if len(tasks[t].recipes[r].resources) > 0 else ['anywhere']),
                *(['following recipe', r] if len(tasks[t].recipes) > 1 else [])
            )
    else:
        print('Solution was not found.')


if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        tasks, resources, params = itemgetter('tasks', 'resources', 'params')(json.load(f))
        solveRCPSP(*_transform(tasks, resources), params)
