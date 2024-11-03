TEMPLATE = """import importlib
import multiprocessing


def call_function_from_file(file_name, function_name, *args, **kwargs):
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

if __name__ == "__main__":
  multiprocessing.freeze_support()
  multiprocessing.set_start_method('spawn')
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

{}

  # Stop the worker process
  task_queue.put("STOP")
  process.join()"""
