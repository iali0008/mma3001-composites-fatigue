# Exploratory specimen-held-out model comparison

MAE is primary. Both specimens have been used in development; neither is an untouched final test set.
MLP entries are the median [minimum, maximum] across all five predeclared seeds, not an ensemble.

| Train -> evaluate | Model | Evaluation MAE | RMSE | R2 | Training MAE |
|---|---|---:|---:|---:|---:|
| L1S11 -> L1S12 | LinearRegression | 0.050532 | 0.058254 | 0.534215 | 0.008395 |
| L1S11 -> L1S12 | DecisionTreeRegressor | 0.105158 | 0.117024 | -0.879715 | 0.009196 |
| L1S11 -> L1S12 | SVR | 0.111193 | 0.126674 | -1.202483 | 0.007352 |
| L1S11 -> L1S12 | MLPRegressor | 0.078193 [0.074266, 0.078196] | 0.087694 [0.082907, 0.087698] | -0.055551 [-0.055653, 0.056549] | 0.008510 |
| L1S11 -> L1S12 | log_cycle_OLS | 0.090299 | 0.105431 | -0.525737 | 0.007362 |
| L1S11 -> L1S12 | DummyRegressor | 0.107731 | 0.119134 | -0.948086 | 0.021370 |
| L1S12 -> L1S11 | LinearRegression | 0.029357 | 0.035001 | -0.911314 | 0.023559 |
| L1S12 -> L1S11 | DecisionTreeRegressor | 0.045803 | 0.051352 | -3.114093 | 0.020342 |
| L1S12 -> L1S11 | SVR | 0.056257 | 0.064136 | -5.417602 | 0.013128 |
| L1S12 -> L1S11 | MLPRegressor | 0.020942 [0.020936, 0.021264] | 0.023866 [0.023453, 0.023872] | 0.111339 [0.110910, 0.141866] | 0.022326 |
| L1S12 -> L1S11 | log_cycle_OLS | 0.092013 | 0.098381 | -14.100526 | 0.027626 |
| L1S12 -> L1S11 | DummyRegressor | 0.083110 | 0.086881 | -10.776416 | 0.080028 |

Full training/evaluation MAE, RMSE and R2 for every seed: metrics.csv. Residual = prediction - observation.
Reference selection ignores target values/availability and reproduces both original cycle-1 references exactly.
Convergence warning records (reported, warm-up and timed fits): 0.
Timing: one warm-up, 15 fresh fits; each prediction timing averages 100 complete held-out-batch calls.
Reported timing medians/IQRs are local warm-process measurements with one numerical-library thread.
Raw-workflow cProfile results are separately stored under raw_profile; they are not model runtimes.

Limitations: two correlated specimen trajectories, few checkpoints, acquisition differences,
unvalidated published stiffness index and prior development exposure. No evaluation-based tuning.
Negative R2 or predictions are retained. Seed ranges are not confidence intervals.
