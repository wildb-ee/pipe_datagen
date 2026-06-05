# pipe_datagen

- **make sure to use .env for DATASET_DIR**
- check_bbimg.py file to check bounding boxes for img
- segmentGen5.py & segmentGen6.py files to generate via *blender* the dataset *(prefs may be edited just based on consts/ RGB, BW for imgs)* 
- convert_segm2bb.py file converts segmentation imgs gen-ed by blender to *bbs* 
- yolo11_ultralytics.ipynb file is basic copy-paste code for ultralytics yolo model training. 

#### NOTE:
 segmentGen5.py *uses material index, cycles instead of eevee, cuda for speedup*
 segmentGen6.py *uses cryptomatte and  eevee*
