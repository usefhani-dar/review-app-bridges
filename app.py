import os
import streamlit as st
from PIL import Image, ImageDraw

# Helper function to parse YOLO label files
def load_yolo_labels(label_content, img_width, img_height):
    """Convert YOLO format labels to pixel coordinates."""
    boxes = []
    classes = []
    for line in label_content.splitlines():
        class_id, x, y, w, h = map(float, line.strip().split())
        # Convert from YOLO format labels to pixel coordinates
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

# Helper function to draw bounding boxes on images
def draw_boxes(image, boxes, classes, class_names):
    """Draw bounding boxes and class labels on the image."""
    draw = ImageDraw.Draw(image)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # Add more colors as needed

    for box, class_id in zip(boxes, classes):
        color = colors[class_id % len(colors)]
        class_name = class_names[class_id] if class_names and class_id < len(class_names) else f"Class {class_id}"
        draw.rectangle(box, outline=color, width=4)
        draw.text((box[0], box[1] - 20), class_name, fill=color)
    return image

# Main Streamlit app
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

    # User-specified base directory for validation folders
    base_directory = st.sidebar.text_input("Enter the base directory for validation folders:", value=os.getcwd())

    # Validation folders
    validation_folders = {
        "Correct": os.path.join(base_directory, "correct"),
        "Incorrect": os.path.join(base_directory, "incorrect"),
        "To Be Deleted": os.path.join(base_directory, "to_delete"),
    }

    # Create validation folders if they don't exist
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
    if "boxes_and_classes" not in st.session_state:
        st.session_state.boxes_and_classes = {}
    if "class_names" not in st.session_state:
        st.session_state.class_names = []

    # Load class names
    if uploaded_class_names:
        class_names_content = uploaded_class_names.read().decode("utf-8")
        st.session_state.class_names = class_names_content.splitlines()
        st.success(f"Loaded {len(st.session_state.class_names)} class names.")

    # Load files
    if st.sidebar.button("Load Files"):
        if not uploaded_images and not uploaded_labels:
            st.error("Please upload images and/or labels.")
            return

        # Add new images to the session state
        if uploaded_images:
            new_images = [img for img in uploaded_images if img.name not in [i.name for i in st.session_state.images]]
            st.session_state.images.extend(new_images)

        # Add new labels to the session state
        if uploaded_labels:
            new_labels = {
                os.path.splitext(label.name)[0]: label
                for label in uploaded_labels
                if os.path.splitext(label.name)[0] not in st.session_state.labels
            }
            st.session_state.labels.update(new_labels)

        st.success(f"Loaded {len(uploaded_images or [])} new images and {len(uploaded_labels or [])} new labels.")

    # Check if images are loaded
    if not st.session_state.images:
        st.warning("No images to review. Please upload images and labels to continue.")
        return

    # Progress counter
    total_images = len(st.session_state.images)
    current_image_index = st.session_state.current_index + 1  # Convert 0-based index to 1-based
    st.write(f"Progress: {current_image_index}/{total_images}")

    # Navigation buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.current_index = (
                st.session_state.current_index - 1
            ) % len(st.session_state.images)

    with col3:
        if st.button("Next ➡️"):
            st.session_state.current_index = (
                st.session_state.current_index + 1
            ) % len(st.session_state.images)

    # Display current image with bounding boxes
    current_image = st.session_state.images[st.session_state.current_index]
    image_name = os.path.splitext(current_image.name)[0]
    label_file = st.session_state.labels.get(image_name)

    img = Image.open(current_image)
    img_width, img_height = img.size

    # Load and store YOLO labels if not already stored
    if image_name not in st.session_state.boxes_and_classes:
        boxes, classes = [], []
        if label_file:
            label_content = label_file.read().decode("utf-8")
            boxes, classes = load_yolo_labels(label_content, img_width, img_height)
        st.session_state.boxes_and_classes[image_name] = (boxes, classes)

    # Retrieve stored bounding boxes and classes
    boxes, classes = st.session_state.boxes_and_classes[image_name]

    img_with_boxes = img.copy()
    if boxes:
        img_with_boxes = draw_boxes(img_with_boxes, boxes, classes, st.session_state.class_names)

    # Display image
    st.image(img_with_boxes, caption=f"{current_image.name} - {len(boxes)} detections")

    # Validation options below the image (horizontal layout)
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
                f.write(current_image.getbuffer())

            if label_file:
                label_path = os.path.join(validation_folder, label_file.name)
                with open(label_path, "wb") as f:
                    f.write(label_file.getbuffer())

            # Show success message
            st.success(f"Image '{current_image.name}' has been successfully moved to the '{validation_status}' folder.")

            # Remove image from session state
            st.session_state.images.pop(st.session_state.current_index)

            # Check if all images are reviewed
            if not st.session_state.images:
                st.session_state.current_index = 0
                st.warning("All images have been reviewed. Please upload more images and labels to continue.")
                return

            # Automatically move to the next image
            st.session_state.current_index %= len(st.session_state.images)
            st.stop()  # Stop execution to simulate a rerun
        else:
            st.error("Invalid validation status.")
    else:
        # Save the selected annotation for persistence
        st.session_state.annotations[image_name] = ["Correct", "Incorrect", "To Be Deleted"].index(validation_status)

if __name__ == "__main__":
    main()
