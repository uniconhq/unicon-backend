import argparse
import os
import sys
import threading

import pika

from unicon_backend.evaluator.project import Project, ProjectAnswers

TASK_RUNNER_OUTPUT_QUEUE_NAME = "task_runner_results"


def listen_to_mq():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    retrieve_channel = connection.channel()
    retrieve_channel.exchange_declare(
        exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, exchange_type="fanout"
    )
    result = retrieve_channel.queue_declare(queue="", exclusive=True)
    queue_name = result.method.queue
    retrieve_channel.queue_bind(
        exchange=TASK_RUNNER_OUTPUT_QUEUE_NAME, queue=queue_name
    )

    def callback(ch, method, properties, body):
        print(f" [x] {body}")

    retrieve_channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True
    )
    retrieve_channel.start_consuming()


if __name__ == "__main__":
    # TODO: properly listen to MQ somewhere else once we have a server instead of running a script
    listening_thread = threading.Thread(target=listen_to_mq, daemon=True)
    listening_thread.start()

    def exit_if(predicate: bool, err_msg: str, exit_code: int = 1) -> None:
        if predicate:
            print(err_msg, file=sys.stderr)
            exit(exit_code)

    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=str, help="Path to the submission file")
    parser.add_argument("answer", type=str, help="Path to the answer file")

    args = parser.parse_args()
    exit_if(not os.path.exists(args.submission), "Submission file not found!")
    exit_if(not os.path.exists(args.answer), "Answer file not found!")

    with open(args.submission) as def_fp:
        project: Project = Project.model_validate_json(def_fp.read())

    with open(args.answer) as answer_fp:
        answer: ProjectAnswers = ProjectAnswers.model_validate_json(answer_fp.read())

    project.run(answer)

    # wait a bit for mq to see results
    listening_thread.join(timeout=5)
