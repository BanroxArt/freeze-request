# Benchmarks

`python bench/run.py` on one core of a cloud VM (Python 3.13), synthetic chains of transfers:

| hops | parse, trace, check, JSON and Markdown |
|---|---|
| 10 | 0.001 s |
| 1,000 | 0.019 s |
| 10,000 | 0.174 s |

Real cases have tens of hops. The numbers are here to show the tool will not be the slow part of a freeze request.
