# Plan:
- find a good location that has good open street view data from mapillary
- Download the street view data from their api
- Find and download the corresponding sentinel 2 data (don't think there is an api)
- find a good zoom level in the satelite images
- decide what to to with multispectrality of the images (depends on the model I use for the satelite image encoding)
- create depth map of the streed view images using some pretrained model?
- package it all in a dataset with the locations such that it is possible to use some kind of contrastive/triplet/ladder loss
