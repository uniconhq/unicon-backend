import argparse
import os
import sys

from unicon_backend.evaluator.project import Project, ProjectAnswers

if __name__ == "__main__":

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
