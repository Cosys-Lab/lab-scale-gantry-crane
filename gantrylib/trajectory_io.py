from abc import ABC, abstractmethod
import csv
from scipy.io import savemat

class TrajectorySerializer(ABC):
    @abstractmethod
    def serialize(self, filename, data, **kwargs):
        pass

class CSVSerializer(TrajectorySerializer):
    def serialize(self, filename, data, columnnames=None, **kwargs):
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            if columnnames:
                writer.writerow(columnnames)
            for row in zip(*data):
                writer.writerow(row)

class MatSerializer(TrajectorySerializer):
    def serialize(self, filename, data, keys=None, **kwargs):
        dic = dict(zip(keys, data)) if keys else data
        savemat(filename, dic)