from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.svm import SVC
from collections import defaultdict
from scipy.interpolate import interp1d
import numpy as np
import matplotlib.pyplot as plt
from utils import shift_right

class CVN(BaseEstimator, ClassifierMixin):

    def __init__(self):
        self._num_windows           = 3
        self._count                 = defaultdict(lambda: defaultdict(int))
        self._ip_metrics_for_window = [dict() for _ in range(self._num_windows)]
        self._n_requests_for_window = [list() for _ in range(self._num_windows)]
        self._Nts                   = list()
        self.plateau_coord          = []

    def _find_plateau(self, window_idx, prob_cumulative):
        x = self._n_requests_for_window[window_idx]
        y = [item * 100 for item in prob_cumulative]
    
        derivative          = np.diff(y) / np.diff(x)
        masked_derivative   = np.ma.masked_equal(derivative, 0)
        min                 = np.min(masked_derivative)
        min_idx             = np.where(derivative == min)[0][0]

        self.plateau_coord.append((x[min_idx], y[min_idx]))

        plt.plot(x, y)
        plt.plot(x[min_idx], y[min_idx], marker='o', markersize=5, color='red', label='Plateau')
        plt.grid()
        plt.title("Probability p(n <= N) = fraction of clients generating max N requests")
        plt.xlabel("Number of requests N")
        plt.ylabel("p(n<=N) %")
        plt.savefig(f"plot_{min_idx}.pdf")
        plt.show()
        
    def _compute_windows(self, X):
        """
        Compute the windows performing a right shift on the unix timestamp.

                Parameters:
                        X (): Dataset of requests made up of timestamp, ip address and unix timestamp.
        """
        for _, row in X.iterrows():
            ip = row['ip']
            for window_idx in range(1, self._num_windows + 1):
                window = shift_right(row['unix_timestamp'], window_idx)
                self._count[window][ip] += 1

    def _aggregate_data(self):
        """
        TODO: Add description
        """
        def merge_dicts(dict1, dict2):
            result = dict1.copy()
            for key, value in dict2.items():
                if key in result:
                    result[key] = max(result[key], value)
                else:
                    result[key] = value
                return result

        for window, ip_metrics in self._count.items():
            # Remove Ni duplicated
            n_requests = list(dict.fromkeys(ip_metrics.values()))
            n_requests.sort()

            match 10 - len(str(window)):
                case 1: # Window 1
                    self._ip_metrics_for_window[0] = merge_dicts(self._ip_metrics_for_window[0], ip_metrics)
                    self._n_requests_for_window[0] = list(set(self._n_requests_for_window[0] + n_requests))
                case 2: # Window 2
                    self._ip_metrics_for_window[1] = merge_dicts(self._ip_metrics_for_window[1], ip_metrics)
                    self._n_requests_for_window[1] = list(set(self._n_requests_for_window[1] + n_requests))
                case 3: # Window 3
                    self._ip_metrics_for_window[2] = merge_dicts(self._ip_metrics_for_window[2], ip_metrics)
                    self._n_requests_for_window[2] = list(set(self._n_requests_for_window[2] + n_requests))

    def _calculate_cumulative_probabilities(self):
        """
        TODO: Add description
        """
        
        for window_idx in range(0, self._num_windows):
            prob_cumulative = []
            for ni in self._n_requests_for_window[window_idx]:
                # Computing: (clients with n <= Ni) / total_sources
                prob = len(
                    [k for k, v in self._ip_metrics_for_window[window_idx].items() if v <= ni]
                ) / len(self._ip_metrics_for_window[window_idx])

                prob_cumulative.append(prob)

            self._find_plateau(window_idx, prob_cumulative)

    def fit(self, X):
        """
        Fitting algorithm. It learns the Nt thresholds for each window driven by the data.

                Parameters:
                        X (): Dataset of requests made up of timestamp, ip address and unix timestamp.

                Returns:
                        self
        """

        self._compute_windows(X)
        self._aggregate_data()
        self._calculate_cumulative_probabilities()

        return self


