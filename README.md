# CookingBuddy
Have you ever wanted to know the *exact*, optimal schedule you should follow when cooking a large meal? No? Why not? You're the weird one, not me.

CookingBuddy provides a script that allows you to define your dinner plans as a constraint satisfaction problem, which CookingBuddy can then solve to *your* satisfaction.

### Explanation
CookingBuddy interprets the general problem of planning out your cooking as a multi-modal RCPSP-Max constraint problem.
This means that, if you can define the tasks you need to do, the dependency graph between them, and the list of resources those tasks use, then CookingBuddy can attempt to determine the optimal schedule of what to do when, using which resources.

#### RCPSP-Max
A **R**esource-**C**onstrained **P**roject **S**cheduling **P**roblem is a kind of scheduling problem where tasks need to be completed using renewable resources, with the goal of using the least amount of time possible to get everything done.
The additional *-Max* qualification means that the constraints placed on the successors also have their own maximum delay.
I've taken a loose interpretation of this and applied it to the presented usecase to mean that every successor constraint can be delayed up-to a certain amount, but no more than that (before the required successor must be scheduled).

#### Multi-modal
Additionally, each task can have multiple modes, or "recipes", specified. This way, you can provide alternative methods for completing the same task, in case one is preferred over the other due to resource constraints.
As an example, you might imagine that one task you might need to perform would be to melt some butter. Normally you might do this on the stovetop in a pot, but you also specify that it can be done in the microwave as well, in case the stove is occupied when you need the melted butter.
Which mode is picked does not, however, have a general affect on the schedule beyond the resource decisions: CookingBuddy adopts a simplified model of the usual RCPSP-Max paradigm, where a specified delay is universal across all modes and is time- and resource-independent.

#### Tasks & Resources
CookingBuddy takes a slightly simplified approach in modelling tasks and resources.
Tasks happen simultaneously given sufficient resources, and there is no minimum distance between tasks (which is unfortunate for those of us who cannot instantly teleport around the kitchen, so they should plan accordingly by padding out task timings).
Resources are considered to be renewable and have no maintenance or cooldown periods (all resources may be used as many times as necessary, are only unavailable when in use, and do not need time between uses).

## Installation
```shell
pipenv install
```

## Usage
```shell
pipenv run python your_file_here.json
```

## File Format
An example JSON file is provided. In general, input files should follow the schema described below:

```ts
/**
 * JSON file.
 */
declare interface Input {
    tasks: Task[],
    resources: Resource[],
    params: { dinner: string } | { start: string }, // timestamp in the shape `HH:mm`
}

/**
 * A task, potentially with nested sub-tasks.
 */
declare interface Task {
    [task: string]: Task | TaskDefinition,
}

/**
 * A definition of a single task.
 */
declare interface TaskDefinition {
    /**
     * Different methods of achieving success on this task.
     */
    recipes: Recipe[],
    /**
     * Optional list of other tasks that depend upon the completion of the current task.
     * An empty or missing list implies that nothing depends on this task.
     */
    successors?: Successor[]
}

/**
 * A method of completing some task.
 */
declare interface Recipe {
    /**
     * How long, in minutes, this recipe takes to complete.
     */
    duration: number,
    /**
     * A list of resources needed to complete this recipe.
     */
    demands: Demand[]
}

/**
 * A tuple containing the name of a task, followed by the maximum delay (in minutes) that is allowed before the
 * successor must be scheduled. 
 * 
 * A delay of `-1` implies that there is no penalty for waiting, so any amount of time may be scheduled between 
 * succeeding tasks.
 * 
 * Task names should be defined using dot syntax, *i.e.* `task.subtask.subsubtask`.
 */
declare type Successor = [string, number];

/**
 * A tuple containing the quantity and name of a required resource.
 */
declare type Demand = [number, string];

/**
 * A renewable, permanent resource, such as an oven or a person.
 * 
 * Requires a unique name and a quantity >= 0.
 */
declare type Resource = [string, number];
```

## Sample Output
```
$ pipenv run pythin sample.json

Optimal schedule will take 04h30m
Start cooking at 12:30 if dinner is to be served by 17:00

                     duck :: 12:30 - 15:30 using [oven]
         green_beans.wash :: 12:30 - 12:35 using [sink, worker]
  stuffing.cornbread.prep :: 12:30 - 12:45 using [counter_top, worker]
turkey.bring_to_room_temp :: 12:30 - 14:30 anywhere
           asparagus.wash :: 12:35 - 12:40 using [sink, worker]
         green_beans.boil :: 12:35 - 12:40 using [burner]
           asparagus.prep :: 12:40 - 12:45 using [counter_top, worker]
        green_beans.shock :: 12:40 - 12:50 anywhere
  stuffing.cornbread.bake :: 12:45 - 13:15 using [oven]
            stuffing.mise :: 12:45 - 13:10 using [counter_top, food_processor, worker]
      turkey.shellac.prep :: 12:45 - 13:05 using [counter_top, worker]
      salad.make_dressing :: 13:05 - 13:10 using [worker]
            stuffing.cook :: 13:10 - 13:30 using [burner, worker]
      sweet_potatoes.prep :: 13:10 - 13:30 using [counter_top, worker]
           asparagus.bake :: 13:15 - 13:30 using [oven]
  stuffing.cornbread.cool :: 13:15 - 13:45 anywhere
               salad.wash :: 13:30 - 13:35 using [sink, worker]
      sweet_potatoes.bake :: 13:30 - 14:00 using [oven]
           salad.assemble :: 13:35 - 13:40 using [counter_top, worker]
   stuffing.cornbread.dry :: 14:00 - 14:30 using [oven]
   turkey.shellac.combine :: 14:25 - 14:40 using [burner, worker]
          turkey.bake.set :: 14:30 - 14:55 using [oven]
              gratin.prep :: 14:40 - 15:20 using [counter_top, worker] following recipe 1
      turkey.bake.baste.1 :: 14:55 - 15:15 using [oven]
      turkey.bake.baste.2 :: 15:15 - 15:35 using [oven]
         stuffing.combine :: 15:25 - 15:35 using [counter_top, worker]
              gratin.bake :: 15:30 - 17:00 using [oven]
      turkey.bake.baste.3 :: 15:35 - 15:55 using [oven]
            stuffing.bake :: 15:55 - 16:55 using [oven]
         turkey.bake.rest :: 15:55 - 16:40 anywhere
```