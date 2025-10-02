import os

# Disable proxy by clearing the environment variables
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""

import io
import streamlit as st
from PIL import Image, ImageDraw

# 1. Cache class names loading
@st.cache_data(show_spinner=False)
def load_class_names(class_names_bytes):
    return class_names_bytes.decode("utf-8").splitlines()

# 2. Cache YOLO label parsing
@st.cache_data(show_spinner=False)
def load_yolo_labels(label_content, img_width, img_height):
    boxes = []
    classes = []
    for line in label_content.splitlines():
        class_id, x, y, w, h = map(float, line.strip().split())
        x = x * img_width
        y = y * img_height
        w = w * img_width
        h = h * img_height
        x1 = int(x - w / 2)
        y1 = int(y - h / 2)
        x2 = int(x + w / 2)
        y2 = int(y + h / 2)
        boxes.append([x1, y1, x2, y2])
        classes.append(int(class_id))
    return boxes, classes

# 3. Cache drawing (expensive if many images)
@st.cache_data(show_spinner=False)
def draw_boxes(image_bytes, boxes, classes, class_names):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    for box, class_id in zip(boxes, classes):
        color = colors[class_id % len(colors)]
        class_name = class_names[class_id] if class_names and class_id < len(class_names) else f"Class {class_id}"
        draw.rectangle(box, outline=color, width=4)
        draw.text((box[0], box[1] - 20), class_name, fill=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

def main():
    st.title("YOLO Image Review App")

    # Sidebar for file uploads
    st.sidebar.header("Upload Files")
    uploaded_images = st.sidebar.file_uploader(
        "Upload Images (Select Multiple)", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )
    uploaded_labels = st.sidebar.file_uploader(
        "Upload Labels (Select Multiple)", type=["txt"], accept_multiple_files=True
    )
    uploaded_class_names = st.sidebar.file_uploader(
        "Upload Class Names (TXT File)", type=["txt"], accept_multiple_files=False
    )

    base_directory = st.sidebar.text_input("Enter the base directory for validation folders:", value=os.getcwd())
    validation_folders = {
        "Correct": os.path.join(base_directory, "correct"),
        "Incorrect": os.path.join(base_directory, "incorrect"),
        "To Be Deleted": os.path.join(base_directory, "to_delete"),
    }

    if st.sidebar.button("Create Validation Folders"):
        if not os.path.exists(base_directory):
            st.sidebar.error(f"The specified base directory does not exist: {base_directory}")
            return
        try:
            for folder in validation_folders.values():
                os.makedirs(folder, exist_ok=True)
            st.sidebar.success(f"Validation folders created in: {base_directory}")
        except Exception as e:
            st.sidebar.error(f"Error creating folders: {e}")
            return

    # Initialize session state for persistence
    if "images" not in st.session_state:
        st.session_state.images = []
    if "labels" not in st.session_state:
        st.session_state.labels = {}
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    if "annotations" not in st.session_state:
        st.session_state.annotations = {}
    if "class_names" not in st.session_state:
        st.session_state.class_names = []
    if "image_bytes" not in st.session_state:
        st.session_state.image_bytes = {}
    if "label_bytes" not in st.session_state:
        st.session_state.label_bytes = {}

    # Load class names (cache)
    if uploaded_class_names:
        st.session_state.class_names = load_class_names(uploaded_class_names.read())
        st.success(f"Loaded {len(st.session_state.class_names)} class names.")

    # Load files (add only new ones)
    if st.sidebar.button("Load Files"):
        if not uploaded_images and not uploaded_labels:
            st.error("Please upload images and/or labels.")
            return

        progress_bar = st.progress(0)  # Initialize progress bar
        total_files = len(uploaded_images or []) + len(uploaded_labels or [])
        processed_files = 0

        if uploaded_images:
            for img in uploaded_images:
                if img.name not in [i.name for i in st.session_state.images]:
                    st.session_state.images.append(img)
                    st.session_state.image_bytes[img.name] = img.getvalue()
                processed_files += 1
                progress_bar.progress(processed_files / total_files)

        if uploaded_labels:
            for label in uploaded_labels:
                label_name = os.path.splitext(label.name)[0]
                if label_name not in st.session_state.labels:
                    st.session_state.labels[label_name] = label
                    st.session_state.label_bytes[label.name] = label.getvalue()
                processed_files += 1
                progress_bar.progress(processed_files / total_files)

        progress_bar.empty()  # Remove the progress bar after processing
        st.success(f"Loaded {len(uploaded_images or [])} new images and {len(uploaded_labels or [])} new labels.")

    if not st.session_state.images:
        st.warning("No images to review. Please upload images and labels to continue.")
        return

    total_images = len(st.session_state.images)
    current_image_index = st.session_state.current_index + 1
    st.write(f"Progress: {current_image_index}/{total_images}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.current_index = (st.session_state.current_index - 1) % total_images
    with col3:
        if st.button("Next ➡️"):
            st.session_state.current_index = (st.session_state.current_index + 1) % total_images

    current_image = st.session_state.images[st.session_state.current_index]
    image_name = os.path.splitext(current_image.name)[0]
    label_file = st.session_state.labels.get(image_name)

    img_bytes = st.session_state.image_bytes[current_image.name]
    img = Image.open(io.BytesIO(img_bytes))
    img_width, img_height = img.size

    # Use spinner for label parsing
    with st.spinner("Parsing labels and drawing boxes..."):
        if label_file:
            label_bytes = st.session_state.label_bytes[label_file.name]
            label_content = label_bytes.decode("utf-8")
            boxes, classes = load_yolo_labels(label_content, img_width, img_height)
        else:
            boxes, classes = [], []

        if boxes:
            img_with_boxes_bytes = draw_boxes(img_bytes, boxes, classes, st.session_state.class_names)
            st.image(img_with_boxes_bytes, caption=f"{current_image.name} - {len(boxes)} detections")
        else:
            st.image(img_bytes, caption=f"{current_image.name} - 0 detections")

    st.subheader("Validation Options")
    validation_status = st.radio(
        "Select Validation Status:",
        ["Correct", "Incorrect", "To Be Deleted"],
        index=st.session_state.annotations.get(image_name, 0),
        horizontal=True
    )

    if st.button("Submit Validation"):
        validation_folder = validation_folders.get(validation_status)
        if validation_folder:
            # Save image and label to the appropriate folder
            image_path = os.path.join(validation_folder, current_image.name)
            with open(image_path, "wb") as f:
                f.write(img_bytes)
            if label_file:
                label_path = os.path.join(validation_folder, label_file.name)
                with open(label_path, "wb") as f:
                    f.write(st.session_state.label_bytes[label_file.name])
            st.success(f"Image '{current_image.name}' has been successfully moved to the '{validation_status}' folder.")
            st.session_state.images.pop(st.session_state.current_index)
            if not st.session_state.images:
                st.session_state.current_index = 0
                st.warning("All images have been reviewed. Please upload more images and labels to continue.")
                return
            st.session_state.current_index %= len(st.session_state.images)
            st.stop()
        else:
            st.error("Invalid validation status.")
    else:
        st.session_state.annotations[image_name] = ["Correct", "Incorrect", "To Be Deleted"].index(validation_status)

if __name__ == "__main__":
    main()
