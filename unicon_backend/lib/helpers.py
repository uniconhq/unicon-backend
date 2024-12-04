from collections.abc import Callable, Sequence


def partition[T](
    predicate: Callable[[T], bool], xs: Sequence[T]
) -> tuple[Sequence[T], Sequence[T]]:
    """Partition a sequence into two sequences based on a predicate"""
    return [x for x in xs if predicate(x)], [x for x in xs if not predicate(x)]
