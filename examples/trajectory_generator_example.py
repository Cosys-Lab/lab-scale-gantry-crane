from gantrylib.trajectory_generator import TrajectoryGenerator
import matplotlib.pyplot as plt

tg = TrajectoryGenerator("crane-properties.yaml")
(t, x, dx, ddx, theta, omega, alpha, u) = tg.generateTrajectory(0, 0.65)
print("dt:")
print(t[1:-1] - t[0:-2])
fig, (ax1, ax2) = plt.subplots(2)
ax1.plot(t, x)
ax1.plot(t, dx)
ax2.plot(t, ddx)
#tg.saveToCSV('testfile.csv', (t, x, dx, ddx, theta, omega, alpha, u), ("t", "x", "v", "a", "theta", "omega", "alpha", "u"))
#tg.saveParamToMat('params.mat')
#tg.saveDataToMat('data.mat', (t, x, dx, ddx, theta, omega, alpha, u), ("t", "x", "v", "a", "theta", "omega", "alpha", "u"))
plt.show()