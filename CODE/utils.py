import warnings
from copy import deepcopy
import cv2
import numpy as np
import visual as vi
from matplotlib import pyplot as plt
from stats import *
import pygcransac


FITTING_ALGS = {"LMEDS": cv2.LMEDS,
                "RANSAC": cv2.RANSAC,
                "LMEDS_FM": cv2.FM_LMEDS,
                "RANSAC_FM": cv2.FM_RANSAC,
                "GC-RANSAC": cv2.USAC_ACCURATE,
                "LO-RANSAC": cv2.USAC_DEFAULT,
                "PROSAC": cv2.USAC_PROSAC,
                "MAGSAC": cv2.USAC_MAGSAC}


def verify_H(src_points, dst_points, threshold, verbose=True, method="LMEDS"):
    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, FITTING_ALGS[method], threshold)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found by ' + method)
    return H, mask.ravel()


def verify_FM(src_points, dst_points, threshold, verbose=True, method="LMEDS", seed=None):
    method = method.upper()
    if method == "LMEDS" or method == "RANSAC": method += "_FM"

    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    if "LMEDS" in method: H, mask = cv2.findFundamentalMat(src_pts, dst_pts, FITTING_ALGS[method], threshold, confidence=0.975)
    else: H, mask = cv2.findFundamentalMat(src_pts, dst_pts, FITTING_ALGS[method], threshold)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found by ' + method)
    return H, mask.ravel()


def verify_pygcransac_H(src_points,dst_points, img1,img2,  threshold, confidence=0.99, spatial_coherence_weight=0.975, neighborhood_size=4, verbose=True):
     """Given src points and dst points and the ransac reprojection error threshold, it estimates the homography using GC RANSAC and returns labels for inliers and outliers


     Args:
       src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
       dst_points: Destination points as a NumPy array (same shape as src_points).
       threshold: The projection error threshold used in the cost function.
       confidence : confidence used to estimate the neighbors in the FAST Approximate Nearest Neighbors algorithm.
       spatial_coherence_weight : weight assigned to the spatial correlation cost function in the energy minimization.
       neighborhood_size : number of neighbors used in the computation of the spatial correlation cost function

     Returns:
       H : homography, (3x3 numpy matrix)
       mask : labels for inlier and outliers    1-inlier ;  0-outlier (numpy array of shape (No_points , )
     """

     kps1,kps2,matches=build_keypts_matches(src_points, dst_points)

     correspondences = np.float32([ (kps1[m.queryIdx].pt + kps2[m.trainIdx].pt) for m in matches ]).reshape(-1,4)
     inlier_probabilities = []

     h1=img1.shape[1]
     w1=img1.shape[0]
     h2=img2.shape[1]
     w2=img2.shape[0]

     H, mask = pygcransac.findHomography(
         np.ascontiguousarray(correspondences),
         h1, w1, h2, w2,
         use_sprt = False,
         threshold=threshold,
         conf=confidence,
         spatial_coherence_weight =spatial_coherence_weight ,
         neighborhood_size = neighborhood_size,
         probabilities = inlier_probabilities,
         sampler = 0,
         use_space_partitioning = True)
     if verbose: print (deepcopy(mask).astype(np.float32).sum(), 'inliers found')
     return H, mask.astype(np.uint8)



def verify_pygcransac_FM(src_points, dst_points, threshold, verbose=True):
    """Given src points and dst points and the ransac reprojection error threshold, it estimates the homography using GC RANSAC and returns labels for inliers and outliers


    Args:
      src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
      dst_points: Destination points as a NumPy array (same shape as src_points).
      threshold: The projection error threshold used in the cost function.
      confidence : confidence used to estimate the neighbors in the FAST Approximate Nearest Neighbors algorithm.
      spatial_coherence_weight : weight assigned to the spatial correlation cost function in the energy minimization.
      neighborhood_size : number of neighbors used in the computation of the spatial correlation cost function

    Returns:
      H : homography, (3x3 numpy matrix)
      mask : labels for inlier and outliers    1-inlier ;  0-outlier (numpy array of shape (No_points , )
    """

    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findFundamentalMat(src_pts, dst_pts, cv2.USAC_ACCURATE, threshold)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found')
    return H, mask.ravel()


def compute_residual(src_, dst_, homography):
    """Given src points and dst points and the homograpgy, it returns the residuals associated to each pair of points


    Args:
      src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
      dst_points: Destination points as a NumPy array (same shape as src_points).
      homography: The homography matrix as a NumPy array (shape: 3x3).

    Returns:
      A NumPy array containing the residual of each pair of points.
    """

    src_ = np.array(src_)
    dst_ = np.array(dst_)
    # Apply the homography to the source points
    projected = projectiveTransform(src_, homography)
    projected = projected.reshape(src_.shape[0], 2)

    # Compute the Euclidean distance between the projected points and the actual destination points
    residuals = (np.sum((projected - dst_) ** 2, axis=1)) ** 0.5

    return residuals


def verify_cv2_H(src_points, dst_points, ransacReprojThreshold=1, verbose=True):
    """Given src points and dst points and the ransac reprojection error threshold, it estimates the homography using RANSAC and returns labels for inliers and outliers


    Args:
      src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
      dst_points: Destination points as a NumPy array (same shape as src_points).
      ransacReprojThreshold: The projection error threshold.

    Returns:
      H : homography, (3x3 numpy matrix)
      mask : labels for inlier and outliers    1-inlier ;  0-outlier (numpy array of shape (No_points , )
    """

    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransacReprojThreshold)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found')
    return H, mask.ravel()


def verify_LMEDS_H(src_points, dst_points, confidence=0.975, verbose=True):
    """Given src points and dst points and the confidence, it estimates the homography using LMEDS and returns labels for inliers and outliers


    Args:
      src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
      dst_points: Destination points as a NumPy array (same shape as src_points).
      confidence: 

    Returns:
      H : homography, (3x3 numpy matrix)
      mask : labels for inlier and outliers    1-inlier ;  0-outlier (numpy array of shape (No_points , )
    """
    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.LMEDS, confidence=confidence)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found')
    return H, mask.ravel()


def verify_cv2_FM(src_points, dst_points, ransacReprojThreshold=1, verbose=True):
    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findFundamentalMat(src_pts, dst_pts, cv2.FM_RANSAC, ransacReprojThreshold)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found')
    return H, mask.ravel()


def verify_LMEDS_FM(src_points, dst_points, confidence=0.975, verbose=True):
    kps1, kps2, matches = build_keypts_matches(src_points, dst_points)
    src_pts = np.float32([kps1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kps2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, mask = cv2.findFundamentalMat(src_pts, dst_pts, cv2.FM_LMEDS, confidence=confidence)
    n_inliers = deepcopy(mask).astype(np.float32).sum()
    if verbose: print(n_inliers, 'inliers found')
    return H, mask.ravel()


def projectiveTransform(points, H):
    """Given a set of points in 2D coordinates it applies the homography H on them.
    Consider d=dimension of points, if 2D points d=2, if 3D points d=3. In our scenario d=2

    Args:
      points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points). shape(N,2) for our instance
      H: Homography.

    Returns:
      (N,1,d) numpy array of points.
    """

    return cv2.perspectiveTransform(points.reshape(-1, 1, 2), H)


def extract_points(models, data):
    """Given the models and the data folder it

    Args:
      models : list of coordinate points of len(models)= Number of models, organized as: assume we want to consider the model 0:
               models[0] is a list of len(models[0])=4 ;

               - models[0][0]= list of coordinates x of points of the model 0, in the first image
               - models[0][1]= list of coordinates y of points of the model 0, in the first image
               - models[0][2]= list of coordinates x of points of the model 0, in the second image
               - models[0][3]= list of coordinates y of points of the model 0, in the second image

      data : single data file from the folder of files

    Returns:
      points :  dictionary of 2D points coordinates for each model. keys= "src_points" and "dst_points"
              - src_points = list of arrays. One array for each model. src_points[0] is an array of points of model 0, shape (N , 2) each                                  point as an array of dim 2 [x_coord , y_coord]
              - dst_points = analogous for dst_points

      inliers1 : numpy array of dim (N,2) with N total number of points. It is a collection of all the points that are inliers in img1.                        Usefull for residual matrix computation
      inliers2: numpy array of dim (N,2) with N total number of points. It is a collection of all the points that are inliers in img2.                        Usefull for residual matrix computation

      labels of inliers : labels only for the inlier points. So for each point in inliers1 or inliers2 we know specifically its model.
    """
    points = {"src_points": [], "dst_points": []}
    for i in range(len(models)):
        src_points = np.array(list(zip(models[i][0], models[i][1])))

        dst_points = np.array(list(zip(models[i][2], models[i][3])))

        points["src_points"].append(src_points)
        points["dst_points"].append(dst_points)

    l = data["label"]
    p = data["data"]
    inl = np.where(l[0] != 0)
    inlp1_x = p[0][inl]
    inlp1_y = p[1][inl]
    inlp2_x = p[3][inl]
    inlp2_y = p[4][inl]

    inliers1 = np.array([inlp1_x, inlp1_y])
    inliers2 = np.array([inlp2_x, inlp2_y])

    return points, np.transpose(inliers1), np.transpose(inliers2), l[0][inl]


def build_keypts_matches(src_points, dst_points):
    src_kpts = [cv2.KeyPoint(x, y, 1) for x, y in src_points]
    dst_kpts = [cv2.KeyPoint(x, y, 1) for x, y in dst_points]
    assert len(src_kpts) == len(dst_kpts)
    matches = [cv2.DMatch(_queryIdx=i, _trainIdx=i, _distance=0) for i in range(len(dst_kpts))]

    return src_kpts, dst_kpts, matches


def draw_matches(img1, img2, src_points, dst_points, title=None, matchColor=(255, 255, 0), singlePointColor=None,
                 flags=2,
                 mask=None, H=None, show_correct=False):
    """ If H and show_correct then the corrected points are shown, according to H"""
    src_kpts, dst_kpts, matches = build_keypts_matches(src_points, dst_points)
    if mask is not None: mask = mask.ravel().tolist()

    draw_params = dict(matchColor=matchColor, singlePointColor=singlePointColor, flags=flags)
    plt.figure(figsize=(12, 8))
    img_out = cv2.drawMatches(img1, src_kpts, img2, dst_kpts, matches, None, matchesMask=mask, **draw_params)
    if H is not None and show_correct:
        dst_correct = projectiveTransform(src_points, H).reshape(src_points.shape[0], 2)

        src_kpts_corr, dst_kpts_corr, matches_corr = build_keypts_matches(src_points, dst_correct)

        img_correct = cv2.drawMatches(img1, src_kpts_corr, img2, dst_kpts_corr, matches_corr, None, matchesMask=mask,
                                      matchColor=(0, 255, 0), singlePointColor=singlePointColor, flags=2)

        img_out = cv2.addWeighted(img_out, 0.6, img_correct, 0.6, 0)

    if title is not None:
        plt.title(title)
    plt.imshow(img_out)
    return

def build_ensemble_mask(data, plot=False, verbose=True, type='H',threshold=None, mask=None):

    img1, img2 = data["img1"], data["img2"]

    outliers, models = vi.group_models(data)["outliers"], vi.group_models(data)["models"]

    points = extract_points(models, data)

    tot_src = points[1]

    points = points[0]
    
    scores=[]

    if threshold is not None: ens_models = [[] for _ in threshold]
        
    labels_ens=[]

    for i in range(len(models)):
        outlier_indexes = []

        if mask is not None:
            src = points["src_points"][i][np.where(mask[i]==1)]
            dst = points["dst_points"][i][np.where(mask[i]==1)]
        else:
            src = points["src_points"][i]
            dst = points["dst_points"][i]

        if threshold is not None:
            for method in ['LMEDS_FM','RANSAC_FM','GC-RANSAC',"LO-RANSAC"]:#,list(FITTING_ALGS.keys())[3:]:
                M, _ = verify_FM(src, dst, threshold=threshold[i], method=method.upper())
                ens_models[i].append(compute_residuals_FM(src, dst, M))
        else:
            for method in ['LMEDS_FM','RANSAC_FM','GC-RANSAC',"LO-RANSAC"]:#list(FITTING_ALGS.keys())[3:]:
                M, _ = verify_FM(src, dst, threshold=threshold, method=method.upper())
                ens_models[i].append(compute_residuals_FM(src, dst, M))

        cv2_mask = np.where(np.sum(np.array(ens_models[i]), axis=0) /4 > threshold[i], 0, 1) #threshold[i]

        src_outl = np.where(cv2_mask == 0)

        outl = src[src_outl]
        
        labels_ens.append(cv2_mask)

        for out in outl:
            for j, arr in enumerate(tot_src):
                if np.array_equal(arr, out):
                    outlier_indexes.append(j)

        print("The outlier indices are", outlier_indexes)

        if plot:
            plt.figure()
            draw_matches(img1, img2, src, dst, matchColor=(255, 0, 0), mask=1 - cv2_mask)
            plt.grid(False)
            plt.show()
            
    return labels_ens


def build_residual_matrix(data, plot=False, verbose=False, type='H', method="lmeds", threshold=None,
                          return_inl_out=False, ensemble=False, show_correct=False, metric="sampson"):
    """Given the data it automatically fit the homography or the fundamental matrix for each model and returns the residual matrix.
        It uses LMEDS.

    Args:

      data : single data file from the folder of files

      plot :  if to plot the points that are considered outliers for the model

      verbose : if to plot the total number of points of the model

      type :  H for Homography, FM for Fundamental matrix

    Returns:
      residual_matrix  : numpy array of shape (Number of points , Number of models). At position i,j there is the residual of point i for                              model j
    """

    assert method.upper() in FITTING_ALGS.keys()

    img1, img2 = data["img1"], data["img2"]

    outliers, models = vi.group_models(data)["outliers"], vi.group_models(data)["models"]

    points = extract_points(models, data)

    tot_src = points[1]

    tot_dst = points[2]

    points = points[0]

    num_of_inliers = np.sum(data["label"] != 0)

    residual_matrix = np.zeros((num_of_inliers, len(models)))

    color = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]

    models_inliers = []

    models_outliers = []

    if threshold is not None and ensemble: ens_models = [[] for _ in threshold]

    for i in range(len(models)):
        outlier_indexes = []

        src = points["src_points"][i]
        dst = points["dst_points"][i]

        if type == 'H':

            if threshold is not None:
                cv2_M, cv2_mask = verify_H(src, dst, threshold=threshold[i], method=method.upper(), verbose=verbose)
            else:
                cv2_M, cv2_mask = verify_H(src, dst, threshold=threshold, method=method.upper(), verbose=verbose)

            src_outl = np.where(cv2_mask == 0)

            outl = src[src_outl]

            for out in outl:
                for j, arr in enumerate(tot_src):
                    if np.array_equal(arr, out):
                        outlier_indexes.append(j)

        elif type == 'FM':

            if threshold is not None:
                cv2_M, cv2_mask = verify_FM(src, dst, threshold=threshold[i], method=method.upper(), verbose=verbose)
            else:
                cv2_M, cv2_mask = verify_FM(src, dst, threshold=threshold, method=method.upper(), verbose=verbose)

            src_outl = np.where(cv2_mask == 0)

            outl = src[src_outl]

            for out in outl:
                for j, arr in enumerate(tot_src):
                    if np.array_equal(arr, out):
                        outlier_indexes.append(j)
        else:
            warnings.warn("The given type is wrong. Types:\n'H'\n'FM'")
            return

        if verbose:
            print("the total number of point is: ", len(src))
            print("The indexes of outlier points are:", outlier_indexes)

        if plot:
            # random_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            plt.figure()

            # color[i % len(color)]

            draw_matches(img1, img2, src, dst, matchColor=(255, 0, 0), mask=1 - cv2_mask, H=cv2_M, show_correct=show_correct)
            plt.grid(False)
            plt.show()

        if type == 'H':
            residual_matrix[:, i] = compute_residual(tot_src, tot_dst, cv2_M)
        elif type == 'FM':
            residual_matrix[:, i] = compute_residuals_FM(tot_src, tot_dst, cv2_M, metric)

        labs, counts = np.unique(cv2_mask, return_counts=True)

        models_inliers.append(counts[np.where(labs == 1)])
        if len(np.where(labs == 1)[0]) > 0:
            models_outliers.append(len(cv2_mask) - counts[np.where(labs == 1)][0])
        else:
            models_outliers.append(len(cv2_mask))

    if return_inl_out:
        return residual_matrix, models_inliers, models_outliers
    else:
        return residual_matrix


def plot_residual_matrix(res,labl=None, show_bar=True,title='Black = Outlier ; White = Inlier'):
        if labl is not None: res=np.hstack((res, labl))
    
        plt.figure(figsize=(20, 10))  # Adjust figure size here
        plt.imshow(res, cmap='hot', interpolation='nearest', aspect="auto")
        if show_bar: 
            cbar = plt.colorbar()  # Add colorbar to show values
            cbar.ax.tick_params(labelsize=10)  # Adjust colorbar label size
            #title="Heatmap"
            

        plt.title(title, fontsize=20)  # Adjust title font size
        plt.xlabel('Models', fontsize=15)  # Adjust x-axis label font size
        plt.ylabel('Points', fontsize=15)  # Adjust y-axis label font size
        plt.show()
        
        return 
    


def soft_clustering_assignment(residual_matrix, thresholds):
    """ Given the residual matrix for an image and the set of thresholds for each model, a soft clustering matrix is created. For each model, 
    the inliers are the points such that their residuals is lower than the threshold of that model. Note, the clustering is soft because the       same point could be inlier for multiple models. 
    
    Args:

      residual_matrix : a numpy array of shape (N,M) where N=number of points, M=number of models

    Returns:
      soft_clustering_matrix  : numpy array of shape (N,M). At position i,j, value of 1 if point i is inlier for model j, 0 otherwise
    """

    assert residual_matrix.shape[1] == len(
        thresholds), "number of models in residual matrix different from numbero of models from threhsolds"
    soft_clustering_assignment = np.zeros(residual_matrix.shape)

    for i in range(len(thresholds)):
        inlier_indexes = np.where(residual_matrix[:, i] < thresholds[i])
        soft_clustering_assignment[inlier_indexes, i] += 1

    return soft_clustering_assignment


def row_compuation(row, fuzzifier=2):
    """ Given a raw of the residual matrix, this function returns a row of the partition matrix.
    
    Args:

      residual_matrix_row : a numpy array of shape (M,), M=number of models

    Returns:
      partition_matrix_row : a numpy array of shape (M,), according to equation (3) in the paper (A fuzzy extension of the silhouette width criterion for cluster analysis ; R.J.G.B. Campello∗, E.R. Hruschka
    """

    new_row = np.zeros(len(row))

    for i in range(len(row)):
        for j in range(len(row)):
            new_row[i] += (row[i] / row[j]) ** (2 / (fuzzifier - 1))

        new_row[i] = new_row[i] ** (-1)
    return new_row


def build_partition_matrix(residual_matrix):
    """ Build the partition Matrix given the residual matrix"""

    partition_matrix = np.zeros(residual_matrix.shape)

    for i in range(residual_matrix.shape[0]):
        partition_matrix[i, :] = row_compuation(residual_matrix[i, :])

    return partition_matrix


def residual_H1_wrt_H2(src, H1, H2):
    """ Compute the residuals of the homography H1 w.r.t homography H2"""

    dst1 = projectiveTransform(src, H1)
    dst2 = projectiveTransform(src, H2)

    dst1 = dst1.reshape(src.shape[0], 2)
    dst2 = dst2.reshape(src.shape[0], 2)

    residuals = (np.sum((dst1 - dst2) ** 2, axis=1)) ** 0.5

    return residuals


def point_belongs_to_model(models, type='H', method='sampson', threshold=1):
    Ms = []
    masks = []

    for i in range(len(models)):
        src_points = np.array(list(zip(models[i][0], models[i][1])))
        dst_points = np.array(list(zip(models[i][2], models[i][3])))
        if type == 'H':
            M, mask = verify_cv2_H(src_points, dst_points)
        elif type == 'FM':
            M, mask = verify_cv2_FM(src_points, dst_points)
        else:
            warnings.warn("Attenzione: nessun tipo valido rilevato. Types: 'H' o 'FM'")
            return
        masks.append(mask)
        Ms.append(M)

    res = compute_residual_different_model(Ms, models, type, method)
    return extract_significant_point_idx(res, threshold)


def extract_significant_point_idx(res, threshold):
    result = {}
    for i in range(len(res)):
        for j in range(len(res[i])):
            if i != j:
                result["model" + str(i + 1) + "_point" + str(j + 1)] = [k for k in range(len(res[i][j])) if
                                                                        res[i][j][k] < threshold]

    return result


def compute_residual_different_model(M, models, type, method):
    residuals = np.zeros((len(models), len(M)), dtype=object)

    for i in range(len(models)):
        for j in range(len(M)):
            if i == j:
                residuals[i][j] = [0]
            else:
                if type == 'H':
                    residuals[i][j] = compute_residual(list(zip(models[i][0], models[i][1])),
                                                       list(zip(models[i][2], models[i][3])),
                                                       M[j])
                elif type == 'FM':
                    residuals[i][j] = compute_residuals_FM(list(zip(models[i][0], models[i][1])),
                                                           list(zip(models[i][2], models[i][3])),
                                                           M[j], method)

    return residuals


def compute_inliers_residual_curve(data, res=None, type='H', return_inl_outl=False, verbose=True, metric="sampson"):
    """Given the data it automatically estimates the homography or the fundamental matrix, compute the residuals and plot the residual curves.        returns residuals of inliers in incremental order.

    Args:

      data : single data file from the folder of files

      type : H for Homography, FM for Fundamental Matrix

    Returns:
     inlier_residuals : list of numpy arrays. One array for model. Each array contains residuals in incremental order.
    """
    outliers, models = vi.group_models(data)["outliers"], vi.group_models(data)["models"]

    points = extract_points(models, data)

    labels = points[3]

    inlier_residuals = []

    if res is None:
        res, inl, outl = build_residual_matrix(data, plot=False, verbose=verbose, type=type, return_inl_out=True, metric=metric)

    for i in range(res.shape[1]):  # for i in range(num of models)

        mod_inliers = np.where(labels == i + 1)[0]  # ground truth of model points

        residuals = np.sort(res[mod_inliers, i])

        inlier_residuals.append(residuals)

    if return_inl_outl:
        return inlier_residuals, inl, outl
    else:
        return inlier_residuals


def plot_inliers_residual_curves(data, res=None):
    """ Plot the residuals in incremental order, for each model in data. Coordinate x is an arange (1,2,3,...etc), coordinate y is -residual value. The negative sign is just because we liked it to be like this ;) """
    residuals = compute_inliers_residual_curve(data, res=res)

    for i in range(len(residuals)):
        mod = residuals[i]

        x_axis = np.arange(len(mod))

        plt.figure()
        plt.scatter(x_axis, -mod, color="b", marker='o')
        plt.xlabel('Points')
        plt.ylabel('Scores')
        plt.title('Scatter Plot of Points')

    return


def plot_res_curve(res, mask, title='Scatter Plot of Points'):
    x_axis = np.arange(len(res))
    blues = np.where(mask == 0)[0]
    reds = np.where(mask == 1)[0]

    plt.figure()
    plt.scatter(x_axis[blues], -res[blues], color="b", marker='o')
    plt.scatter(x_axis[reds], -res[reds], color="r", marker='o')
    plt.xlabel('Points')
    plt.ylabel('Scores')
    plt.title(title)

    return


def calculate_reprojection_error(src_points, dst_points, M, inlier_mask, type):
    """
    This function calculates the reprojection error for points transformed using a homography.

    Args:
      src_points: Source points as a NumPy array (shape: Nx2 or Nx3, where N is the number of points).
      dst_points: Destination points as a NumPy array (same shape as src_points).
      M: The homography matrix as a NumPy array (shape: 3x3).
      inlier_mask: A mask indicating inlier points (1 for inlier, 0 for outlier) as a NumPy array (same length as src_points).

    Returns:
      A NumPy array containing the reprojection errors for each point (only for inliers based on the mask).
    """

    if type == 'H':
        # Project source points using the homography
        # projected_points = cv2.perspectiveTransform(src_points[inlier_mask].reshape(-1, 1, 2), M)

        # Calculate the reprojection error (distance between actual and projected destination points)
        # reprojection_errors = np.linalg.norm(projected_points[:, 0, :] - dst_points[inlier_mask], axis=1)
        reprojection_errors = compute_residual(src_points[inlier_mask], dst_points[inlier_mask], M)
    elif type == 'FM':
        reprojection_errors = compute_residuals_FM(src_points[inlier_mask], dst_points[inlier_mask], M)
    else:
        return
    return reprojection_errors


def analyze_reprojection_error(data, thresholds=None, method="LMEDS", type='H'):
    """
    This function analyzes the average reprojection error for inliers after fitting with LMEDS at different thresholds.

    Args:
      data: A tuple containing source and destination points (src_points, dst_points).
      thresholds: A list of inlier thresholds to evaluate.

    Returns:
      A dictionary where keys are thresholds and values are the average reprojection errors for inliers at that threshold.
    """
    if thresholds is None:
        thresholds = [1]
    outliers, models = vi.group_models(data)["outliers"], vi.group_models(data)["models"]

    points = extract_points(models, data)
    src_points, dst_points, lab = points[1], points[2], points[3]
    average_errors = {}
    for l in np.unique(lab):
        assert method.upper() in FITTING_ALGS.keys()
        if type == 'H':
            # Fit the model (homography) using LMEDS
            M, mask = verify_H(src_points[lab == l],
                               dst_points[lab == l],
                               thresholds[l - 1],
                               method=method.upper())
        elif type == 'FM':
            M, mask = verify_FM(src_points[lab == l],
                                dst_points[lab == l],
                                thresholds[l - 1],
                                method=method.upper())

        inlier_mask = mask.ravel() > 0  # Convert mask to 1D array with True for inliers

        # Calculate reprojection errors and compute the average for inliers only
        reprojection_errors = calculate_reprojection_error(src_points[lab == l],
                                                           dst_points[lab == l],
                                                           M,
                                                           inlier_mask,
                                                           type)
        average_errors[thresholds[l - 1]] = np.mean(reprojection_errors)
    return average_errors


def compute_sampson_distance(src_points, dst_points, F):
    src_ = np.array(src_points)
    dst_ = np.array(dst_points)
    F = np.array(F, dtype=np.float64)

    # Convert source point to homogeneous coordinates
    src_points_hom = np.array([np.append(src_point, 1) for src_point in src_], dtype=np.float64)

    # Convert destination points to homogeneous coordinates
    dst_points_hom = np.array([np.append(dst_point, 1) for dst_point in dst_], dtype=np.float64)

    return np.array([cv2.sampsonDistance(src_point_hom, dst_point_hom, F) for src_point_hom, dst_point_hom in
                     zip(src_points_hom, dst_points_hom)])


def distance_point_line(ps, ls):
    return np.array([np.dot(np.array(l), np.array(p).T) / np.sqrt(l[0] ** 2 + l[1] ** 2) for l, p in zip(ls, ps)])


def compute_SED(src_points, dst_points, F):
    src_ = np.array(src_points)
    dst_ = np.array(dst_points)

    # Convert source point to homogeneous coordinates
    src_points_hom = np.array([np.append(src_point, 1) for src_point in src_])

    # Convert destination points to homogeneous coordinates
    dst_points_hom = np.array([np.append(dst_point, 1) for dst_point in dst_])

    # Compute the epilines of the source points
    ep_ls = np.array([np.dot(F.T, dst_point_hom.T) for dst_point_hom in dst_points_hom])

    # Compute the epilines of the destination points
    ep_ls_prime = np.array([np.dot(F, src_point_hom.T) for src_point_hom in src_points_hom])

    return np.sqrt(
        distance_point_line(src_points_hom, ep_ls) ** 2 + distance_point_line(dst_points_hom, ep_ls_prime) ** 2)


def compute_residuals_FM(src_points, dst_points, F, method='sampson'):
    if method == 'sampson':
        return compute_sampson_distance(src_points, dst_points, F)
    if method == 'sed':
        return compute_SED(src_points, dst_points, F)


def plot_forward_search(src_points, dst_points, title='', type='H'):
    if type == 'H':
        M, mask = verify_LMEDS_H(src_points, dst_points)
        scores = np.sort(compute_residual(src_points, dst_points, M))

    elif type == 'FM':

        M, mask = verify_LMEDS_FM(src_points, dst_points)
        scores = np.sort(compute_residuals_FM(src_points, dst_points, M))

    unique, counts = np.unique(mask, return_counts=True)

    # Perform forward search
    _, threshold = forward_search(residuals=scores,
                                  initial_m0=len(mask) - counts[np.where(unique == 1)][0] + 1)

    # Plot actual scores
    plt.plot(range(1, len(scores) + 1), scores)

    # Calculate approximate envelopes using order statistics
    group_size = len(scores) // 10  # Divide into groups of 10% of total correspondences
    min_scores = [min(scores[i:i + group_size]) for i in range(0, len(scores), group_size)]
    max_scores = [max(scores[i:i + group_size]) for i in range(0, len(scores), group_size)]
    x_values = np.arange(1, len(scores) + 1, group_size)
    f_min = interp1d(x_values, min_scores, kind='previous')
    f_max = interp1d(x_values, max_scores, kind='previous')

    # Plot approximate envelopes
    plt.plot(x_values, f_min(x_values), 'r--', label='Lower Envelope')
    plt.plot(x_values, f_max(x_values), 'g--', label='Upper Envelope')

    plt.axhline(threshold, linestyle='--')

    plt.xlabel('Number of Correspondences')
    plt.ylabel('Residual Scores')
    plt.title('Forward Search with Approximate Envelopes ' + title)
    plt.legend()
    plt.grid(True)
    plt.show()

    return threshold
