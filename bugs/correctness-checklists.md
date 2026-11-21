# Correctness checklists for the core set (F1), 10 bugs

Written 2026-11-21, **before any LLM patch for these bugs was seen** (only requests-3179 had LLM patches in stage 1; its checklist is marked).
Sources are the bug report or commit message, the developer's test, and the docs. They are never the developer's patch code, and never an LLM patch.
How to use: when labelling a plausible patch, check each item by reading the patch (or by running it, where marked **[test]**). A patch is *correct* only if every item holds.
**[test]** marks items that are cheap to turn into an extra test later.

---

## requests-3179: `Response.json` (models.py)
Source: commit message "self.content could be None, so len(self.content) may raise TypeError"; developer test `test_response_json_when_content_is_None`.
Note: LLM patches for this bug were already seen in stage 1 (C1 and C4), so this checklist is not blind for requests-3179. Say so in the report.
1. If `r.content` is `None`, `r.json()` raises `ValueError` (a JSON decode error), not `TypeError`. **[test]**
2. A normal response with JSON bytes and no encoding set still decodes, e.g. content `b'{"a": 1}'` gives `{"a": 1}`. **[test]**
3. Encoding guessing for UTF-16/32 JSON without an encoding is not removed. Only the `None` case changes.

## requests-3368: `Response.iter_content` (models.py)
Source: PR title "Allow None value for chunk_size again"; developer test `test_response_chunk_size_type`.
1. `iter_content(None)` on raw `b'the content'` yields the whole content: `list(...) == [b'the content']`. **[test]**
2. `iter_content(1)` still yields 1-byte chunks.
3. A non-int, non-None `chunk_size` (e.g. `"1"` or `2.0`) still raises `TypeError`. **[test]**

## requests-3390: `check_header_validity` (utils.py)
Source: PR "Defining header value type requirements" (issue #3386); developer test `test_header_value_not_str`.
1. A header value of type `int`, `dict` or `list` raises `requests.exceptions.InvalidHeader`, not a bare `TypeError`. **[test]**
2. `str` and `bytes` values that are valid (e.g. `'bar baz'`, `b'fbbq'`, `''`) are still accepted.
3. A value with a leading space or a `\r`/`\n` still raises `InvalidHeader` (the injection check is kept).

## requests-4723: `should_bypass_proxies` (utils.py)
Source: PR "Fix assumed hostname when using a 'file' URI scheme adapter"; developer test case `('file:///some/path/on/disk', True)`.
1. `should_bypass_proxies('file:///some/path/on/disk', no_proxy=None)` returns `True` without raising. **[test]**
2. The existing cases in `test_should_bypass_proxies` keep their results (e.g. `http://172.16.1.12/` gives `False`, and a host in `no_proxy` gives `True`).
3. The fix does not swallow every exception. An HTTP URL with a hostname still goes through the `no_proxy` matching.

## luigi-3: `TupleParameter.parse` (parameter.py)
Source: commit "Fix parsing for TupleParameter" (#2619, fixes #2609, an error with dynamic dependencies); developer test `testSerialize`.
1. `TupleParameter().parse(TupleParameter().serialize((1, 2, 3))) == (1, 2, 3)`, so a flat tuple round-trips. **[test]**
2. A tuple of tuples still round-trips: `((1, 2), (3, 4))`.
3. The literal syntax still parses: `parse('((12,3),(4,15))') == ((12, 3), (4, 15))` (from the class docstring).

## luigi-4: `S3CopyToTable.copy` (contrib/redshift.py)
Source: commit "Allow NoneType columns in Redshift COPY job" (fixes #2298); developer tests `test_s3_copy_with_nonetype_columns`, `..._default_columns`, `..._valid_columns`.
1. With `columns=None`, `copy` runs and issues `COPY` with an empty column list (`colnames=''`). **[test]**
2. With `columns=[]`, it behaves the same as `None`.
3. With real columns, the column list is still `(some_text,some_int)`.

## luigi-14: `Task.has_excessive_failures` (scheduler.py), multi-function developer fix
Source: commit "Scheduler crashes for some configs: when 'disable_hard_timeout' is set but 'disable_failures' is not"; developer test `test_no_crash_on_only_disable_hard_timeout`.
1. A scheduler with `disable_hard_timeout=100` and no `disable_failures` does not crash when a task fails, and the task is handed out again after the retry delay. **[test]**
2. With `disable_failures=N` set, a task is still disabled after N failures.
3. With `disable_hard_timeout` set, a task that keeps failing past the timeout is still disabled.

## luigi-22: `Worker.__init__` (scheduler.py)
Source: commit "Fix the TypeError whenever prune is called before update has been invoked in worker"; developer test `test_worker_prune_after_init`.
1. `Worker(123).prune(cfg)` right after creation does not raise. **[test]**
2. A worker created just now is not treated as stale: `last_active` is about the creation time, so a freshly created worker is not pruned.
3. A worker that has been inactive longer than `worker_disconnect_delay` is still pruned.
Note: item 2 is about behaviour. The developer's version (`last_active=time.time()` as a default argument) sets the time once, at import. A patch that sets it per worker is at least as correct, so don't mark it wrong just for differing from the developer.

## luigi-25: `S3CopyToTable.run` (contrib/redshift.py)
Source: PR "Fix for #995"; developer test `test_s3_copy_to_table` ("check that the `S3CopyToTable.s3_load_path` class attribute was successfully referenced in `run`").
1. When `s3_load_path` is a string attribute, `run()` does not raise, and `copy` is called with `(cursor, task.s3_load_path)`. **[test]**
2. `run()` still checks that the table exists, with the same SQL, and creates it if missing.
3. A missing `table` still raises the "table need to be specified" error.

## luigi-26: `HadoopJarJobRunner.run_job` (contrib/hadoop_jar.py)
Source: commit "fix a simple crash in logging when jar() not defined"; developer test `test_missing_jar`.
1. A job whose `jar()` returns `None` raises `HadoopJarJobError`, not `TypeError`. **[test]**
2. A job whose jar path does not exist on disk still raises `HadoopJarJobError`.
3. A job with an existing jar file still runs (`test_good`).

---

## Excluded: luigi-6
Excluded from the core set on 2026-11-21 (see bugs/core-set.txt). Its checklist is kept for the record.

### luigi-6: `ListParameter.serialize` (parameter.py), multi-function developer fix
Source: commit "Fix ListParameter Hashability" (#2227): "Ensure lists of dictionaries can be serialized and parsed as ListParameters", "Add support for tuples of dictionaries"; developer tests `test_list_dict`, `test_tuple_dict`.
1. A task with `ListParameter` value `[{'foo': 'bar'}, {'doge': 'wow'}]` can be created, and its value hashes equal to `p.normalize(p.parse('[{"foo": "bar"}, {"doge": "wow"}]'))`. **[test]**
2. The same holds for `TupleParameter` with `({'foo': 'bar'}, {'doge': 'wow'})`.
3. Plain lists (`[1, "hello"]`) and nested lists still behave as before.
Warning: item 2 needs `TupleParameter` values to be normalised (made hashable). In the buggy code, `TupleParameter` has no `normalize` of its own, so a patch that only edits `ListParameter.serialize` probably cannot pass `test_tuple_dict`. This comes from reading the code; it hasn't been run.

