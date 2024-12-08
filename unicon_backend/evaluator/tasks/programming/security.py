import libcst as cst

WORKER_TEMPLATE = cst.parse_module("""
import os
from contextlib import redirect_stdout
def call_function_from_file(file_name, function_name, *args, **kwargs):
    with open(os.devnull, "w") as f:
        with redirect_stdout(f):  
            module_name = file_name.replace(".py", "")
            module = importlib.import_module(module_name)
            func = getattr(module, function_name)
            return func(*args, **kwargs)


def worker(task_queue, result_queue):
    while True:
        task = task_queue.get()
        if task == "STOP":
            break

        file_name, function_name, args, kwargs = task
        try:
            result = call_function_from_file(file_name, function_name, *args, **kwargs)
            result_queue.put(result)
        except Exception as e:
            result_queue.put(e)
""")

ENTRYPOINT_TEMPLATE = cst.parse_module("""
multiprocessing.freeze_support()
multiprocessing.set_start_method("spawn")
task_queue = multiprocessing.Queue()
result_queue = multiprocessing.Queue()

process = multiprocessing.Process(target=worker, args=(task_queue, result_queue))
process.start()

def call_function_safe(file_name, function_name, *args, **kwargs):
    task_queue.put((file_name, function_name, args, kwargs))
    result = result_queue.get()
    # TODO: handle properly
    if isinstance(result, Exception):
        raise result
    return result
""")

MPI_CLEANUP_TEMPLATE = cst.parse_module("""
task_queue.put("STOP")
process.join()
""")


def mpi_sandbox(program: cst.Module) -> cst.Module:
    return cst.Module(
        [
            cst.parse_statement("import importlib, multiprocessing"),
            *WORKER_TEMPLATE.body,
            cst.If(
                test=cst.parse_expression("__name__ == '__main__'"),
                body=cst.IndentedBlock(
                    [*ENTRYPOINT_TEMPLATE.body, *program.body, *MPI_CLEANUP_TEMPLATE.body]
                ),
            ),
        ]
    )
