# Overview

Jarvis streamlines the process of task execution planning based on user-defined goals. Beyond that, it efficiently translates these tasks into JVM instructions, allowing seamless integration and execution.

## How to Use Jarvis 

### Generating a Task Execution Plan

For Direct Input Goals. Generate a plan for task execution directly from provided input goals:

```
python -m jarvis --replan
```

Using a Goal File. If you have predefined goals stored in a file, place this file in the 'workspace' directory. To generate a plan based on this file:

```
python -m jarvis --replan --goalfile=<GOALFILE>
```

### Translating Tasks to JVM Instructions

Translate All Tasks. Convert all tasks in the execution plan into their corresponding JVM instructions:

```
python -m jarvis
```

Translate Specific Task. If you wish to only translate a task with a particular task number:

```
python -m jarvis --compile=<task_num>
```

## Executing JVM Instructions

Execute JVM instructions based on the specified task. Here are a couple of examples:

```
python -m jarvis --yaml=1.yaml
python -m jarvis --yaml=2.yaml
```