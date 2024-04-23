from stats import *

class Inlier_Thresholder:

    ########### initialize the object with the 1D array of values
    def __init__(self, values):
        self.values = values
        self.threshold = None
        self.methods = ["IQR", "Median AD", "Variance based" ,"Rosseeuw SN", "Rosseeuw QN"]#, "First Jump","DBSCAN"]
        self.internal_validation_measures = ["Silhouette", "BSS", "WSS"]

    ########### specify the method among the available ones and return the labels
    def compute_inlier_threshold(self, method):

        assert method in self.methods

        if method == "IQR":
            return interquantile_outlier(self.values)

        if method == "DBSCAN":
            return anomaly_detection_DBSCAN(self.values)
        if method == "Median AD":
            return Median_Absolute_Deviation(self.values)
        if method == "Variance based":
            return Variance_based(self.values)

        if method == "First Jump":
            return First_Jump(self.values)

        if method == "Rosseeuw SN":
            return rousseeuwcroux_SN(self.values)
        if method == "Rosseeuw QN":
            return rousseeuwcroux_QN(self.values)

        return

    ########### Majority voting ensemble
    def ensemble_inlier_thresholder(self):

        L = []

        for met in self.methods:
            tmp, _ = self.compute_inlier_threshold(met)
            threshold = np.array(tmp)
            threshold[threshold == None] = 0.90
            L.append(threshold)

        sums = np.array([sum(values) for values in zip(*L)])

        #### sums>=5 if more than 4 models agree
        return (sums >= 5).astype(int)

    ############## Select the internal validation measure as an objective function
    ############## Return the method that optimize the internal validation measure
    ############## Default is Silhouette: empirically the best one

    def use_best_method(self, internal_validation_measure="Silhouette"):

        assert internal_validation_measure in self.internal_validation_measures

        score_sil = []  # score for the silhouette

        score_sep = []  # score for the separation BSS

        score_coh = []  # score for the cohesion WSS

        for met in self.methods:
            lab, _ = self.compute_inlier_threshold(met)

            if len(np.unique(lab)) == 1:
                score_sil.append(0), score_sep.append(0)
            else:

                silhouette_avg = silhouette_score(self.values.reshape(-1, 1), lab)
                wss, bss = compute_wss_bss(self.values, lab)

                score_sil.append(silhouette_avg)
                score_sep.append(bss)
                score_coh.append(wss)

        lab = self.ensemble_inlier_thresholder()

        if len(np.unique(lab)) == 1:
            score_sil.append(0), score_sep.append(0)
        else:
            silhouette_avg = silhouette_score(self.values.reshape(-1, 1), lab)
            wss, bss = compute_wss_bss(self.values, lab)

            score_sil.append(silhouette_avg)
            score_sep.append(bss)
            score_coh.append(wss)

        if internal_validation_measure == "Silhouette": to_use = np.argmax(score_sil)
        if internal_validation_measure == "BSS": to_use = np.argmax(score_sep)
        if internal_validation_measure == "WSS": to_use = np.argmin(score_coh)

        if to_use < len(self.methods):
            print(self.methods[to_use])

            return self.compute_inlier_threshold(self.methods[to_use])

        if to_use == len(self.methods):
            print("Ensemble")
            return self.ensemble_inlier_thresholder()
