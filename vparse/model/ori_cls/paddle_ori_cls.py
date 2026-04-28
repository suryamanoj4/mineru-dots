# Copyright (c) Opendatalab. All rights reserved.
import os

from PIL import Image
from collections import defaultdict
from typing import List, Dict
from tqdm import tqdm
import cv2
import numpy as np
import onnxruntime

from vparse.utils.enum_class import ModelPath
from vparse.utils.models_download_utils import auto_download_and_get_model_root_path


class PaddleOrientationClsModel:
    def __init__(self, ocr_engine):
        self.sess = onnxruntime.InferenceSession(
            os.path.join(auto_download_and_get_model_root_path(ModelPath.paddle_orientation_classification), ModelPath.paddle_orientation_classification)
        )
        self.ocr_engine = ocr_engine
        self.less_length = 256
        self.cw, self.ch = 224, 224
        self.std = [0.229, 0.224, 0.225]
        self.scale = 0.00392156862745098
        self.mean = [0.485, 0.456, 0.406]
        self.labels = ["0", "90", "180", "270"]

    def preprocess(self, input_img):
        # Upscale image so the shortest side is 256
        h, w = input_img.shape[:2]
        scale = 256 / min(h, w)
        h_resize = round(h * scale)
        w_resize = round(w * scale)
        img = cv2.resize(input_img, (w_resize, h_resize), interpolation=1)
        # Resize to 224x224 square
        h, w = img.shape[:2]
        cw, ch = 224, 224
        x1 = max(0, (w - cw) // 2)
        y1 = max(0, (h - ch) // 2)
        x2 = min(w, x1 + cw)
        y2 = min(h, y1 + ch)
        if w < cw or h < ch:
            raise ValueError(
                f"Input image ({w}, {h}) smaller than the target size ({cw}, {ch})."
            )
        img = img[y1:y2, x1:x2, ...]
        # Normalization
        split_im = list(cv2.split(img))
        std = [0.229, 0.224, 0.225]
        scale = 0.00392156862745098
        mean = [0.485, 0.456, 0.406]
        alpha = [scale / std[i] for i in range(len(std))]
        beta = [-mean[i] / std[i] for i in range(len(std))]
        for c in range(img.shape[2]):
            split_im[c] = split_im[c].astype(np.float32)
            split_im[c] *= alpha[c]
            split_im[c] += beta[c]
        img = cv2.merge(split_im)
        # 5. Convert to CHW format
        img = img.transpose((2, 0, 1))
        imgs = [img]
        x = np.stack(imgs, axis=0).astype(dtype=np.float32, copy=False)
        return x

    def predict(self, input_img):
        rotate_label = "0"  # Default to 0 if no rotation detected or not portrait
        if isinstance(input_img, Image.Image):
            np_img = np.asarray(input_img)
        elif isinstance(input_img, np.ndarray):
            np_img = input_img
        else:
            raise ValueError("Input must be a pillow object or a numpy array.")
        bgr_image = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
        # First check the overall image aspect ratio (height/width)
        img_height, img_width = bgr_image.shape[:2]
        img_aspect_ratio = img_height / img_width if img_width > 0 else 1.0
        img_is_portrait = img_aspect_ratio > 1.2

        if img_is_portrait:

            det_res = self.ocr_engine.ocr(bgr_image, rec=False)[0]
            # Check if table is rotated by analyzing text box aspect ratios
            if det_res:
                vertical_count = 0
                is_rotated = False

                for box_ocr_res in det_res:
                    p1, p2, p3, p4 = box_ocr_res

                    # Calculate width and height
                    width = p3[0] - p1[0]
                    height = p3[1] - p1[1]

                    aspect_ratio = width / height if height > 0 else 1.0

                    # Count vertical vs horizontal text boxes
                    if aspect_ratio < 0.8:  # Taller than wide - vertical text
                        vertical_count += 1
                    # elif aspect_ratio > 1.2:  # Wider than tall - horizontal text
                    #     horizontal_count += 1

                if vertical_count >= len(det_res) * 0.28 and vertical_count >= 3:
                    is_rotated = True
                # logger.debug(f"Text orientation analysis: vertical={vertical_count}, det_res={len(det_res)}, rotated={is_rotated}")

                # If we have more vertical text boxes than horizontal ones,
                # and vertical ones are significant, table might be rotated
                if is_rotated:
                    x = self.preprocess(np_img)
                    (result,) = self.sess.run(None, {"x": x})
                    rotate_label = self.labels[np.argmax(result)]
                    # logger.debug(f"Orientation classification result: {label}")

        return rotate_label

    def list_2_batch(self, img_list, batch_size=16):
        """
        Split a list of any length into multiple batches based on a specified batch size

        Args:
            img_list: Input list
            batch_size: Size of each batch, defaults to 16

        Returns:
            A list containing multiple batches, each a sublist of the original list
        """
        batches = []
        for i in range(0, len(img_list), batch_size):
            batch = img_list[i : min(i + batch_size, len(img_list))]
            batches.append(batch)
        return batches

    def batch_preprocess(self, imgs):
        res_imgs = []
        for img_info in imgs:
            img = np.asarray(img_info["table_img"])
            # Upscale image so the shortest side is 256
            h, w = img.shape[:2]
            scale = 256 / min(h, w)
            h_resize = round(h * scale)
            w_resize = round(w * scale)
            img = cv2.resize(img, (w_resize, h_resize), interpolation=1)
            # Resize to 224x224 square
            h, w = img.shape[:2]
            cw, ch = 224, 224
            x1 = max(0, (w - cw) // 2)
            y1 = max(0, (h - ch) // 2)
            x2 = min(w, x1 + cw)
            y2 = min(h, y1 + ch)
            if w < cw or h < ch:
                raise ValueError(
                    f"Input image ({w}, {h}) smaller than the target size ({cw}, {ch})."
                )
            img = img[y1:y2, x1:x2, ...]
            # Normalization
            split_im = list(cv2.split(img))
            std = [0.229, 0.224, 0.225]
            scale = 0.00392156862745098
            mean = [0.485, 0.456, 0.406]
            alpha = [scale / std[i] for i in range(len(std))]
            beta = [-mean[i] / std[i] for i in range(len(std))]
            for c in range(img.shape[2]):
                split_im[c] = split_im[c].astype(np.float32)
                split_im[c] *= alpha[c]
                split_im[c] += beta[c]
            img = cv2.merge(split_im)
            # 5. Convert to CHW format
            img = img.transpose((2, 0, 1))
            res_imgs.append(img)
        x = np.stack(res_imgs, axis=0).astype(dtype=np.float32, copy=False)
        return x

    def batch_predict(
        self, imgs: List[Dict], det_batch_size: int, batch_size: int = 16
    ) -> None:

        import torch
        from packaging import version
        if version.parse(torch.__version__) >= version.parse("2.8.0"):
            return None

        """
        Batch predict rotation for the provided image information list and correctly reorient any rotated images.
        """
        RESOLUTION_GROUP_STRIDE = 128
        # Skip images with aspect ratio < 1.2
        resolution_groups = defaultdict(list)
        for img in imgs:
            # Convert RGB image to BGR
            bgr_img: np.ndarray = cv2.cvtColor(np.asarray(img["table_img"]), cv2.COLOR_RGB2BGR)
            img["table_img_bgr"] = bgr_img
            img_height, img_width = bgr_img.shape[:2]
            img_aspect_ratio = img_height / img_width if img_width > 0 else 1.0
            if img_aspect_ratio > 1.2:
                # Normalize dimensions to multiples of RESOLUTION_GROUP_STRIDE
                normalized_h = ((img_height + RESOLUTION_GROUP_STRIDE) // RESOLUTION_GROUP_STRIDE) * RESOLUTION_GROUP_STRIDE  # Round up to the nearest multiple of RESOLUTION_GROUP_STRIDE
                normalized_w = ((img_width + RESOLUTION_GROUP_STRIDE) // RESOLUTION_GROUP_STRIDE) * RESOLUTION_GROUP_STRIDE
                group_key = (normalized_h, normalized_w)
                resolution_groups[group_key].append(img)

        # Batch process each resolution group
        rotated_imgs = []
        for group_key, group_imgs in tqdm(resolution_groups.items(), desc="Table-ori cls stage1 predict", disable=True):
            # Calculate target size (max dimensions within group, rounded up to RESOLUTION_GROUP_STRIDE multiple)
            max_h = max(img["table_img_bgr"].shape[0] for img in group_imgs)
            max_w = max(img["table_img_bgr"].shape[1] for img in group_imgs)
            target_h = ((max_h + RESOLUTION_GROUP_STRIDE - 1) // RESOLUTION_GROUP_STRIDE) * RESOLUTION_GROUP_STRIDE
            target_w = ((max_w + RESOLUTION_GROUP_STRIDE - 1) // RESOLUTION_GROUP_STRIDE) * RESOLUTION_GROUP_STRIDE

            # Pad all images to uniform dimensions
            batch_images = []
            for img in group_imgs:
                bgr_img = img["table_img_bgr"]
                h, w = bgr_img.shape[:2]
                # Create a white background with target dimensions
                padded_img = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255
                # Paste original image in top-left corner
                padded_img[:h, :w] = bgr_img
                batch_images.append(padded_img)

            # Batch detection
            batch_results = self.ocr_engine.text_detector.batch_predict(
                batch_images, min(len(batch_images), det_batch_size)
            )

            # Detect rotation based on batch results; add rotated images to list for further angle prediction.

            for index, (img_info, (dt_boxes, elapse)) in enumerate(
                zip(group_imgs, batch_results)
            ):
                vertical_count = 0
                for box_ocr_res in dt_boxes:
                    p1, p2, p3, p4 = box_ocr_res

                    # Calculate width and height
                    width = p3[0] - p1[0]
                    height = p3[1] - p1[1]

                    aspect_ratio = width / height if height > 0 else 1.0

                    # Count vertical text boxes
                    if aspect_ratio < 0.8:  # Taller than wide - vertical text
                        vertical_count += 1

                if vertical_count >= len(dt_boxes) * 0.28 and vertical_count >= 3:
                    rotated_imgs.append(img_info)

        # Predict rotation angle for rotated images
        if len(rotated_imgs) > 0:
            imgs = self.list_2_batch(rotated_imgs, batch_size=batch_size)
            with tqdm(total=len(rotated_imgs), desc="Table-ori cls stage2 predict", disable=True) as pbar:
                for img_batch in imgs:
                    x = self.batch_preprocess(img_batch)
                    results = self.sess.run(None, {"x": x})
                    for img_info, res in zip(rotated_imgs, results[0]):
                        label = self.labels[np.argmax(res)]
                        self.img_rotate(img_info, label)
                        pbar.update(1)

    def img_rotate(self, img_info, label):
        if label == "270":
            img_info["table_img"] = cv2.rotate(
                np.asarray(img_info["table_img"]),
                cv2.ROTATE_90_CLOCKWISE,
            )
            img_info["wired_table_img"] = cv2.rotate(
                np.asarray(img_info["wired_table_img"]),
                cv2.ROTATE_90_CLOCKWISE,
            )
        elif label == "90":
            img_info["table_img"] = cv2.rotate(
                np.asarray(img_info["table_img"]),
                cv2.ROTATE_90_COUNTERCLOCKWISE,
            )
            img_info["wired_table_img"] = cv2.rotate(
                np.asarray(img_info["wired_table_img"]),
                cv2.ROTATE_90_COUNTERCLOCKWISE,
            )
        else:
            # No processing for 180 and 0 degrees
            pass
