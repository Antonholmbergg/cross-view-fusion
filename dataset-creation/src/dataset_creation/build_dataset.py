import lance
import numpy as np
import pyarrow as pa


def test_lance() -> None:
    table = pa.Table.from_pydict(
        {"a": np.arange(10), "b": np.arange(5, 15), "c": np.ones(10)}
    )
    lance.write_dataset(table, "test.lance")


if __name__ == "__main__":
    test_lance()
