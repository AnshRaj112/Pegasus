# Top 50 Functions (cProfile by `tottime`)

**Source:** `docs/benchmarks/profile-stats.pstats`

| Rank | Function | File | Call Count | Total Time (s) | Avg Time (ms) | % Runtime |
|------|----------|------|------------|----------------|-----------------|-----------|
| 1 | `decode_compare_payload` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/spill.py:41` | 170,000 | 3.4234 | 0.0201 | 15.6% |
| 2 | `encode_compare_payload_values` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/spill.py:30` | 170,000 | 3.3054 | 0.0194 | 15.0% |
| 3 | `<built-in method builtins.len>` | `~:0` | 7,051,684 | 1.7869 | 0.0003 | 8.1% |
| 4 | `encode_record` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/spill.py:61` | 170,000 | 1.2699 | 0.0075 | 5.8% |
| 5 | `<method 'unpack_from' of '_struct.Struct' objects>` | `~:0` | 1,700,000 | 1.2325 | 0.0007 | 5.6% |
| 6 | `<method 'decode' of 'bytes' objects>` | `~:0` | 1,360,002 | 1.0605 | 0.0008 | 4.8% |
| 7 | `decode_record` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/spill.py:78` | 170,000 | 0.9636 | 0.0057 | 4.4% |
| 8 | `<method 'pack' of '_struct.Struct' objects>` | `~:0` | 1,700,000 | 0.9432 | 0.0006 | 4.3% |
| 9 | `run` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/pipeline.py:121` | 1 | 0.7611 | 761.0517 | 3.5% |
| 10 | `<method 'encode' of 'str' objects>` | `~:0` | 1,360,013 | 0.7605 | 0.0006 | 3.5% |
| 11 | `split_line` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/flat_file.py:233` | 170,004 | 0.7353 | 0.0043 | 3.3% |
| 12 | `iter_partition` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/spill.py:173` | 170,128 | 0.6789 | 0.0040 | 3.1% |
| 13 | `<method 'append' of 'list' objects>` | `~:0` | 1,411,874 | 0.5860 | 0.0004 | 2.7% |
| 14 | `<method 'split' of 'str' objects>` | `~:0` | 170,529 | 0.3833 | 0.0022 | 1.7% |
| 15 | `<method 'read' of '_io.BufferedReader' objects>` | `~:0` | 340,131 | 0.3371 | 0.0010 | 1.5% |
| 16 | `_write_frame_partitions` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/polars_spill.py:76` | 2 | 0.2870 | 143.5149 | 1.3% |
| 17 | `_fp_hash_to_bytes` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/polars_spill.py:53` | 170,000 | 0.2860 | 0.0017 | 1.3% |
| 18 | `parse_lines` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/flat_file.py:296` | 2 | 0.2495 | 124.7266 | 1.1% |
| 19 | `_fields` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/flat_file.py:321` | 170,002 | 0.2125 | 0.0013 | 1.0% |
| 20 | `<method 'collect' of 'builtins.PyLazyFrame' objects>` | `~:0` | 6 | 0.1940 | 32.3309 | 0.9% |
| 21 | `<built-in method new_str>` | `~:0` | 46 | 0.1845 | 4.0110 | 0.8% |
| 22 | `<method 'startswith' of 'bytes' objects>` | `~:0` | 170,000 | 0.1829 | 0.0011 | 0.8% |
| 23 | `<method 'to_list' of 'builtins.PySeries' objects>` | `~:0` | 1,152 | 0.1730 | 0.1502 | 0.8% |
| 24 | `<method 'extend' of 'bytearray' objects>` | `~:0` | 170,128 | 0.1528 | 0.0009 | 0.7% |
| 25 | `<method 'join' of 'bytes' objects>` | `~:0` | 170,000 | 0.1487 | 0.0009 | 0.7% |
| 26 | `_flat_parse_to_polars` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/in_memory.py:146` | 2 | 0.1459 | 72.9394 | 0.7% |
| 27 | `<method 'get' of 'dict' objects>` | `~:0` | 210,229 | 0.1412 | 0.0007 | 0.6% |
| 28 | `<method 'to_bytes' of 'int' objects>` | `~:0` | 170,000 | 0.1412 | 0.0008 | 0.6% |
| 29 | `_load_delimited_frame` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/in_memory.py:173` | 2 | 0.1278 | 63.8947 | 0.6% |
| 30 | `<built-in method _struct.unpack>` | `~:0` | 170,000 | 0.1240 | 0.0007 | 0.6% |
| 31 | `<built-in method _struct.pack>` | `~:0` | 170,000 | 0.1087 | 0.0006 | 0.5% |
| 32 | `try_partition_side_polars` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/polars_spill.py:152` | 2 | 0.0866 | 43.2771 | 0.4% |
| 33 | `<method 'rstrip' of 'str' objects>` | `~:0` | 170,020 | 0.0839 | 0.0005 | 0.4% |
| 34 | `<method 'ljust' of 'bytes' objects>` | `~:0` | 170,000 | 0.0822 | 0.0005 | 0.4% |
| 35 | `<method 'strip' of 'str' objects>` | `~:0` | 170,020 | 0.0760 | 0.0004 | 0.3% |
| 36 | `<method 'add' of 'set' objects>` | `~:0` | 70,134 | 0.0653 | 0.0009 | 0.3% |
| 37 | `<built-in method builtins.isinstance>` | `~:0` | 178,998 | 0.0640 | 0.0004 | 0.3% |
| 38 | `collect` | `/home/ansh.raj/.pyenv/versions/3.12.13/lib/python3.12/site-packages/polars/lazyframe/frame.py:2279` | 6 | 0.0560 | 9.3329 | 0.3% |
| 39 | `_construct_series_with_fallbacks` | `/home/ansh.raj/.pyenv/versions/3.12.13/lib/python3.12/site-packages/polars/_utils/construction/series.py:345` | 46 | 0.0326 | 0.7082 | 0.1% |
| 40 | `<method 'replace' of 'str' objects>` | `~:0` | 5 | 0.0295 | 5.9081 | 0.1% |
| 41 | `<method 'write' of '_io.BufferedWriter' objects>` | `~:0` | 128 | 0.0287 | 0.2238 | 0.1% |
| 42 | `to_list` | `/home/ansh.raj/.pyenv/versions/3.12.13/lib/python3.12/site-packages/polars/series/series.py:4673` | 1,152 | 0.0230 | 0.0200 | 0.1% |
| 43 | `_fp_equal` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/pipeline.py:94` | 50,000 | 0.0183 | 0.0004 | 0.1% |
| 44 | `__exit__` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/pipeline/timing.py:62` | 10,135 | 0.0183 | 0.0018 | 0.1% |
| 45 | `<built-in method _io.open>` | `~:0` | 261 | 0.0153 | 0.0586 | 0.1% |
| 46 | `<method 'partition_by' of 'builtins.PyDataFrame' objects>` | `~:0` | 2 | 0.0139 | 6.9371 | 0.1% |
| 47 | `<built-in method posix.unlink>` | `~:0` | 129 | 0.0116 | 0.0899 | 0.1% |
| 48 | `<built-in method time.perf_counter>` | `~:0` | 20,274 | 0.0100 | 0.0005 | 0.0% |
| 49 | `split_physical_lines` | `/home/ansh.raj/Pegasus/pegasus-backend/src/pegasus/validation/flat_file.py:34` | 2 | 0.0091 | 4.5493 | 0.0% |
| 50 | `<built-in method builtins.getattr>` | `~:0` | 10,229 | 0.0083 | 0.0008 | 0.0% |

Sorted by **self time** (`tottime`). Cumulative time in parent report.
