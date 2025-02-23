# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# More info: https://github.com/ejnunn/PPE-Object-Detection

import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import os, urllib
import sys
try:
    sys.path.append('/usr/local/lib64/python3.6/site-packages')
    import cv2
except Exception as e:
    print(e)
st.set_option('deprecation.showfileUploaderEncoding', False)

# Streamlit encourages well-structured code, like starting execution in a main() function.
def main():
    # Render the readme as markdown using st.markdown.
    readme_text = st.markdown(get_file_content_as_string("instructions.md"))

    # Download external dependencies.
    for filename in EXTERNAL_DEPENDENCIES.keys():
        download_file(filename)

    # Once we have the dependencies, add a selector for the app mode on the sidebar.
    st.sidebar.title("What to do")
    app_mode = st.sidebar.selectbox("Choose the app mode",
        ["Show overview", "Run the app", "Show the source code"])
    if app_mode == "Show overview":
        st.sidebar.success('To continue select "Run the app".')
    elif app_mode == "Show the source code":
        readme_text.empty()
        st.code(get_file_content_as_string("app.py"))
    elif app_mode == "Run the app":
        readme_text.empty()
        run_the_app()

# This file downloader demonstrates Streamlit animation.
def download_file(file_path):
    # Don't download the file twice. (If possible, verify the download using the file length.)
    if os.path.exists(file_path):
        if "size" not in EXTERNAL_DEPENDENCIES[file_path]:
            return
        elif os.path.getsize(file_path) == EXTERNAL_DEPENDENCIES[file_path]["size"]:
            return

    # These are handles to two visual elements to animate.
    weights_warning, progress_bar = None, None
    try:
        weights_warning = st.warning("Downloading %s..." % file_path)
        progress_bar = st.progress(0)
        with open(file_path, "wb") as output_file:
            with urllib.request.urlopen(EXTERNAL_DEPENDENCIES[file_path]["url"]) as response:
                length = int(response.info()["Content-Length"])
                counter = 0.0
                MEGABYTES = 2.0 ** 20.0
                while True:
                    data = response.read(8192)
                    if not data:
                        break
                    counter += len(data)
                    output_file.write(data)

                    # We perform animation by overwriting the elements.
                    weights_warning.warning("Downloading %s... (%6.2f/%6.2f MB)" %
                        (file_path, counter / MEGABYTES, length / MEGABYTES))
                    progress_bar.progress(min(counter / length, 1.0))

    # Finally, we remove these visual elements by calling .empty().
    finally:
        if weights_warning is not None:
            weights_warning.empty()
        if progress_bar is not None:
            progress_bar.empty()

# This is the main app app itself, which appears when the user selects "Run the app".
def run_the_app():
    # Select which images you want to run the inference on
    dataset = st.sidebar.selectbox('Select dataset', ['Training Data', 'Testing Data', 'Upload Image'])
    if dataset == 'Upload Image':
        run_on_upload()
    elif dataset == 'Training Data':
        run_on_data(TRAIN_DATA_URL_ROOT)
    elif dataset == 'Testing Data':
        run_on_data(TEST_DATA_URL_ROOT)
    

def run_on_data(data_path):
    # To make Streamlit fast, st.cache allows us to reuse computation across runs.
    # In this common pattern, we download data from an endpoint only once.
    @st.cache
    def load_metadata(filepath):
        return pd.read_csv(filepath)

    # This function uses some Pandas magic to summarize the metadata Dataframe.
    @st.cache
    def create_summary(metadata):
        one_hot_encoded = pd.get_dummies(metadata[["image", "label"]], columns=["label"])
        summary = one_hot_encoded.groupby(["image"]).sum().rename(columns={
            "label_Hard Hat": "Hard Hat",
            "label_Safety Vest": "Safety Vest"
        })
        return summary

    # An amazing property of st.cached functions is that you can pipe them into
    # one another to form a computation DAG (directed acyclic graph). Streamlit
    # recomputes only whatever subset is required to get the right answer!
    metadata = load_metadata(data_path + "labels.csv")
    summary = create_summary(metadata)

    # Draw the UI elements to search for objects (pedestrians, cars, etc.)
    #selected_frame_index, selected_frame = frame_selector_ui(summary)
    #if selected_frame_index == None:
    #    st.error("No frames fit the criteria. Please select different label or number.")
    #    return

    # Draw the UI element to select an image to view
    total_frames = len([x for x in os.listdir(data_path + 'obj/') if x[-4:] == '.jpg'])
    selected_frame = st.sidebar.slider('Choose an image (index)', 1, total_frames, 1)

    # Draw the UI element to select parameters for the YOLO object detector.
    confidence_threshold, overlap_threshold = object_detector_ui()

    # Load the image from file.
    image_url = os.path.join(data_path + 'obj/', 'frame-' + str(selected_frame).zfill(3) + '.jpg')
    image = load_image(image_url)

    # Get the boxes for the objects detected by YOLO by running the YOLO model.
    yolo_boxes = yolo_v3(image, confidence_threshold, overlap_threshold)
    draw_image_with_boxes(image, yolo_boxes, "Real-time Computer Vision",
        "**YOLO v3 Model** (overlap `%3.1f`) (confidence `%3.1f`)" % (overlap_threshold, confidence_threshold))

    # Draw ground truth boxes on the image
    try:
        boxes = metadata[metadata['image'] == 'frame-' + str(selected_frame).zfill(3) + '.jpg'].drop(columns=["image"])
        min_max_boxes = boxes
        draw_image_with_boxes(image, boxes, "Ground Truth",
            "**Human-annotated data** (image `%s`)" % selected_frame)
    except:
        pass

    # Draw the UI elements for metadata details
    st.sidebar.subheader('Metadata Details')

    display_metadata = st.sidebar.checkbox('Show metadata and summary')
    display_boxes = st.sidebar.checkbox('Show bounding box coordinates') 
    if display_metadata:
        display_metadata_state = st.write('## Metadata', metadata[:1000], '## Summary', summary[:1000])
    if display_boxes:
        st.write('## Bounding Boxes', boxes)

def run_on_upload():
    # Draw the UI element to select an image to view
    uploaded_image = st.file_uploader('Upload an image', type='jpg')

    # Draw the UI element to select parameters for the YOLO object detector.
    confidence_threshold, overlap_threshold = object_detector_ui()

    if uploaded_image != None:
        # Load the image from file.
        #image = load_image(uploaded_image)
        file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
        image = cv2.cvtColor(cv2.imdecode(file_bytes, cv2.COLOR_BGR2RGB), cv2.COLOR_BGR2RGB)
        
        # Get the boxes for the objects detected by YOLO by running the YOLO model.
        yolo_boxes = yolo_v3(image, confidence_threshold, overlap_threshold)
        draw_image_with_boxes(image, yolo_boxes, "Real-time Computer Vision",
            "**YOLO v3 Model** (overlap `%3.1f`) (confidence `%3.1f`)" % (overlap_threshold, confidence_threshold))

# This sidebar UI is a little search engine to find certain object types.
def frame_selector_ui(summary):
    st.sidebar.markdown("# Frame")

    # The user can pick which type of object to search for.
    object_type = st.sidebar.selectbox("Search for which objects?", summary.columns, 0)

    # The user can select a range for how many of the selected objecgt should be present.
    min_elts, max_elts = st.sidebar.slider("How many %ss (select a range)?" % object_type, 0, 15, [3, 6])
    selected_frames = get_selected_frames(summary, object_type, min_elts, max_elts)
    if len(selected_frames) < 1:
        return None, None

    # Choose a frame out of the selected frames.
    selected_frame_index = st.sidebar.slider("Choose an image (index)", 0, len(selected_frames) - 1, 0)

    # Draw an altair chart in the sidebar with information on the frame.
    objects_per_frame = summary.loc[selected_frames, object_type].reset_index(drop=True).reset_index()
    chart = alt.Chart(objects_per_frame, height=120).mark_area().encode(
        alt.X("index:Q", scale=alt.Scale(nice=False)),
        alt.Y("%s:Q" % object_type))
    selected_frame_df = pd.DataFrame({"selected_frame": [selected_frame_index]})
    vline = alt.Chart(selected_frame_df).mark_rule(color="red").encode(
        alt.X("selected_frame:Q", axis=None)
    )
    st.sidebar.altair_chart(alt.layer(chart, vline))

    selected_frame = selected_frames[selected_frame_index]
    return selected_frame_index, selected_frame

# Select frames based on the selection in the sidebar
@st.cache(hash_funcs={np.ufunc: str})
def get_selected_frames(summary, label, min_elts, max_elts):
    return summary[np.logical_and(summary[label] >= min_elts, summary[label] <= max_elts)].index

# This sidebar UI lets the user select parameters for the YOLO object detector.
def object_detector_ui():
    st.sidebar.markdown("# Model")
    confidence_threshold = st.sidebar.slider("Confidence threshold", 0.0, 1.0, 0.75, 0.01)
    overlap_threshold = st.sidebar.slider("Overlap threshold", 0.0, 1.0, 0.5, 0.01)
    return confidence_threshold, overlap_threshold

# Draws an image with boxes overlayed to indicate the presence of PPE, people etc.
def draw_image_with_boxes(image, boxes, header, description):
    # Superpose the semi-transparent object detection boxes.    # Colors for the boxes
    LABEL_COLORS = {
        "Hard Hat": [0, 255, 0],    # green
        "Safety Vest": [255, 0, 0]  # red
    }
    image_with_boxes = image.astype(np.float64)
    for _, (label, xmin, xmax, ymin, ymax) in boxes.iterrows():
        image_with_boxes[int(ymin):int(ymax),int(xmin):int(xmax),:] += LABEL_COLORS[label]
        image_with_boxes[int(ymin):int(ymax),int(xmin):int(xmax),:] /= 2

    # Draw the header and image.
    st.subheader(header)
    st.markdown(description)
    st.image(image_with_boxes.astype(np.uint8), use_column_width=True)
    st.write('Bounding Box Coordinates', boxes)

# Download a single file and make its content available as a string.
@st.cache(show_spinner=False)
def get_file_content_as_string(path):
    url = 'https://raw.githubusercontent.com/ejnunn/PPE-Object-Detection/master/' + path
    response = urllib.request.urlopen(url)
    return response.read().decode("utf-8")

# This function loads an image from local storage. Use st.cache on this
# function as well, so you can reuse the images across runs.
@st.cache(show_spinner=False)
def load_image(path):
    image = cv2.imread(path)
    image = image[:, :, [2, 1, 0]] # BGR -> RGB
    return image

# Run the YOLO model to detect objects.
def yolo_v3(image, confidence_threshold, overlap_threshold):
    # Load the network. Because this is cached it will only happen once.
    @st.cache(allow_output_mutation=True)
    def load_network(config_path, weights_path):
        net = cv2.dnn.readNetFromDarknet(config_path, weights_path)
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
        return net, output_layers
    net, output_layers = load_network("yolov3_ppe2.cfg", "yolov3_ppe2_last.weights")

    # Run the YOLO neural net.
    blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (416, 416), (0,0,0), swapRB=True, crop=False)
    net.setInput(blob)
    layer_outputs = net.forward(output_layers)

    # Supress detections in case of too low confidence or too much overlap.
    boxes, confidences, class_IDs = [], [], []
    H, W = image.shape[:2]
    for out in layer_outputs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > confidence_threshold:
                center_x = int(detection[0] * W)
                center_y = int(detection[1] * H)
                w = int(detection[2] * W)
                h = int(detection[3] * H)
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                class_IDs.append(class_id)
                confidences.append(float(confidence))
                boxes.append([x, y, w, h])
    indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, overlap_threshold)

    # Map from YOLO labels to PPE labels.
    PPE_LABELS = {
        0: 'Hard Hat',
        1: 'Safety Vest'
    }
    labels, xmin, ymin, xmax, ymax = [], [], [], [], []
    if len(indices) > 0:
        # loop over the indexes we are keeping
        for i in indices.flatten():
            label = PPE_LABELS.get(class_IDs[i], None)
            if label is None:
                continue

            # extract the bounding box coordinates
            box = boxes[i]
            x1, y1, w, h = box[0], box[1], box[2], box[3]
            xmin.append(x1)
            xmax.append(x1+w)
            ymin.append(y1)
            ymax.append(y1+h)
            labels.append(label)

    boxes = pd.DataFrame({"label": labels, "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax})
    return boxes[["label", "xmin", "xmax", "ymin", "ymax"]]


# Path to the Streamlit public S3 bucket
TRAIN_DATA_URL_ROOT = "./train_data/"
TEST_DATA_URL_ROOT = "./test_data/"

# External files to download.
EXTERNAL_DEPENDENCIES = {
    "yolov3_ppe2_last.weights": {
        "url": "https://ppe-object-detection.s3.us-east-2.amazonaws.com/yolov3_ppe2_last.weights",
        "size": 246326928
    },
    "yolov3_ppe2.cfg": {
        "url": "https://raw.githubusercontent.com/ejnunn/PPE-Object-Detection/master/yolov3-ppe.cfg",
        "size": 8336
    }
}

if __name__ == "__main__":
    main()
