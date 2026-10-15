# Multi-slice demo images

Real slices grouped by patient, for trying the **multi-slice** upload (choose all slices in one patient folder).

- Source: Cheng, J. *brain tumor dataset*. figshare. https://doi.org/10.6084/m9.figshare.1512427 (licence: CC BY 4.0). Described in Cheng, J., et al. (2015), *PLoS ONE* 10(10): e0140381.
- Converted from the original MATLAB files to 512×512 grayscale JPG (intensity scaled to 0–255); no other changes.
- 5 patients per tumour class (meningioma, glioma, pituitary), up to 5 slices each, chosen at random with a fixed seed. The dataset has no 'no tumour' class.
- These slices are part of the Kaggle dataset the model was trained on, so the model has very likely seen them: use them to **demonstrate** the feature, not to measure accuracy.
