# 1. Define initial guesses based on your uv.txt data
E0 = -164.0
V0 = 74.5
B0 = 0.5
Bp = 4.0

# 2. Corrected Murnaghan EOS energy function
murn(x) = E0 + (V0 * B0 / Bp) * (((V0 / x)**Bp) / (Bp - 1.0) + (x / V0) - (1.0 / (Bp - 1.0)))

# 3. Perform the non-linear least-squares fit
fit murn(x) 'uv.txt' u 2:3 via E0, V0, B0, Bp

# 4. Plot the data points alongside the fitted curve
plot 'uv.txt' u 2:3 title 'DFT Data' pt 7 ps 0.5, murn(x) title 'Murnaghan Fit' lw 2