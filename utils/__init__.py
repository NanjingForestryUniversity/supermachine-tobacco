# -*- codeing = utf-8 -*-
# Time : 2022/7/18 9:46
# @Auther : zhouchao
# @File: utils.py
# @Software:PyCharm
import glob
import logging
import os
import pathlib
import time
from datetime import datetime
from queue import Queue

import cv2
import numpy as np
from numpy.random import default_rng
from matplotlib import pyplot as plt
import re

from config import Config


def natural_sort(l):
    """
    自然排序
    :param l: 待排序
    :return:
    """
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


class MergeDict(dict):
    def __init__(self):
        super(MergeDict, self).__init__()

    def merge(self, merged: dict):
        for k, v in merged.items():
            if k not in self.keys():
                self.update({k: v})
            else:
                original = self.__getitem__(k)
                new_value = np.concatenate([original, v], axis=0)
                self.update({k: new_value})
        return self


class ImgQueue(Queue):
    """
        A custom queue subclass that provides a :meth:`clear` method.
    """

    def clear(self):
        """
        Clears all items from the queue.
        """

        with self.mutex:
            unfinished = self.unfinished_tasks - len(self.queue)
            if unfinished <= 0:
                if unfinished < 0:
                    raise ValueError('task_done() called too many times')
                self.all_tasks_done.notify_all()
            self.unfinished_tasks = unfinished
            self.queue.clear()
            self.not_full.notify_all()

    def safe_put(self, item):
        if self.full():
            _ = self.get()
            return False
        self.put(item)
        return True


def read_labeled_img(dataset_dir: str, color_dict: dict, ext='.bmp', is_ps_color_space=True) -> dict:
    """
    根据dataset_dir下的文件创建数据集

    :param dataset_dir: 文件夹名称，文件夹内必须包含'label'和'label'两个文件夹，并分别存放同名的图像与标签
    :param color_dict: 进行标签图像的颜色查找
    :param ext: 图片后缀名,默认为.bmp
    :param is_ps_color_space: 是否使用ps的标准lab色彩空间，默认True
    :return: 字典形式的数据集{label: vector(n x 3)},vector为lab色彩空间
    """
    img_names = [img_name for img_name in os.listdir(os.path.join(dataset_dir, 'label'))
                 if img_name.endswith(ext)]
    total_dataset = MergeDict()
    for img_name in img_names:
        img_path, label_path = [os.path.join(dataset_dir, folder, img_name) for folder in ['img', 'label']]
        # 读取图片和色彩空间转换
        img = cv2.imread(img_path)
        label_img = cv2.imread(label_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        # 从opencv的色彩空间到Photoshop的色彩空间
        if is_ps_color_space:
            alpha, beta = np.array([100 / 255, 1, 1]), np.array([0, -128, -128])
            img = img * alpha + beta
            img = np.asarray(np.round(img, 0), dtype=int)
        dataset = {label: img[np.all(label_img == color, axis=2)] for color, label in color_dict.items()}
        total_dataset.merge(dataset)
    return total_dataset


def lab_scatter(dataset: dict, class_max_num=None, is_3d=False, is_ps_color_space=True, **kwargs):
    """
    在lab色彩空间内绘制3维数据分布情况

    :param dataset: 字典形式的数据集{label: vector(n x 3)},vector为lab色彩空间
    :param class_max_num: 每个类别最多画的样本数量，默认不限制
    :param is_3d: 进行lab三维绘制或者a,b两通道绘制
    :param is_ps_color_space: 是否使用ps的标准lab色彩空间，默认True
    :return: None
    """
    # 观察色彩分布情况
    if "alpha" not in kwargs.keys():
        kwargs["alpha"] = 0.1
    if 'inside_alpha' in kwargs.keys():
        inside_alpha = kwargs['inside_alpha']
    else:
        inside_alpha = kwargs["alpha"]
    if 'outside_alpha' in kwargs.keys():
        outside_alpha = kwargs['outside_alpha']
    else:
        outside_alpha = kwargs["alpha"]
    fig = plt.figure()
    if is_3d:
        ax = fig.add_subplot(projection='3d')
    else:
        ax = fig.add_subplot()
    for label, data in dataset.items():
        if label == 'Inside':
            alpha = inside_alpha
        elif label == 'Outside':
            alpha = outside_alpha
        else:
            alpha = kwargs["alpha"]
        if class_max_num is not None:
            assert isinstance(class_max_num, int)
            if data.shape[0] > class_max_num:
                sample_idx = np.arange(data.shape[0])
                sample_idx = np.random.choice(sample_idx, class_max_num)
                data = data[sample_idx, :]
        l, a, b = [data[:, i] for i in range(3)]
        if is_3d:
            ax.scatter(a, b, l, label=label, alpha=alpha)
        else:
            ax.scatter(a, b, label=label, alpha=alpha)
    x_max, x_min, y_max, y_min, z_max, z_min = [127, -127, 127, -127, 100, 0] if is_ps_color_space else \
        [255, 0, 255, 0, 255, 0]
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel('a*')
    ax.set_ylabel('b*')
    if is_3d:
        ax.set_zlim(z_min, z_max)
        ax.set_zlabel('L')
    plt.legend()
    plt.show()


def size_threshold(img, blk_size, threshold, last_end: np.ndarray = None) -> np.ndarray:
    mask = img.reshape(img.shape[0], img.shape[1] // blk_size, blk_size).sum(axis=2). \
        reshape(img.shape[0] // blk_size, blk_size, img.shape[1] // blk_size).sum(axis=1)
    mask[mask <= threshold] = 0
    mask[mask > threshold] = 1
    if last_end is not None:
        half_blk_size = blk_size // 2
        assert (last_end.shape[0] == half_blk_size) and (last_end.shape[1] == img.shape[1])
        mask_up = np.concatenate((last_end, img[:-half_blk_size, :]), axis=0)
        mask_up_right = np.concatenate((mask_up[:, half_blk_size:],
                                        np.zeros((img.shape[0], half_blk_size), dtype=np.uint8)), axis=1)
        mask_up = size_threshold(mask_up, blk_size, threshold)
        mask_up_right = size_threshold(mask_up_right, blk_size, threshold)
        mask[:-1, :] = mask_up[1:, :]
        mask[:-1, 1:] = mask_up_right[1:, :-1]
    return mask


def valve_merge(img: np.ndarray, merge_size: int = 2) -> np.ndarray:
    assert img.shape[1] % merge_size == 0  # 列数必须能够被整除
    img_shape = (img.shape[1], img.shape[0])
    img = img.reshape((img.shape[0], img.shape[1] // merge_size, merge_size))
    img = np.sum(img, axis=2)
    img[img > 0] = 1
    img = cv2.resize(img.astype(np.uint8), dsize=img_shape)
    return img


def valve_expend(img: np.ndarray) -> np.ndarray:
    kernel = np.ones((1, Config.valve_horizontal_padding), np.uint8)
    img = cv2.dilate(img, kernel, iterations=1)
    return img


def shield_valve(mask: np.ndarray, left_shield: int = -1, right_shield: int = -1) -> np.asarray:
    if (left_shield < mask.shape[1]) & (left_shield > 0):
        mask[:, :left_shield] = 0
    if (right_shield < mask.shape[1]) & (right_shield > 0):
        mask[:, -right_shield:] = 0
    return mask


def valve_limit(mask: np.ndarray, max_valve_num: int) -> np.ndarray:
    """
    用于限制阀门同时开启个数的函数
    :param mask: 阀门开启mask,0,1格式，每个1对应一个阀门
    :param max_valve_num: 最大阀门数量
    :return:
    """
    assert (max_valve_num >= 1) and (max_valve_num < 50)
    row_valve_count = np.sum(mask, axis=1)
    if np.any(row_valve_count > max_valve_num):
        over_rows_idx = np.argwhere(row_valve_count > max_valve_num).ravel()
        logging.warning(f'发现单行喷阀数量{len(over_rows_idx)}超过限制，已限制到最大许可值{max_valve_num}')
        over_rows = mask[over_rows_idx, :]

        # a simple function to get lucky valves when too many valves appear in the same line
        def process_row(each_row):
            valve_idx = np.argwhere(each_row > 0).ravel()
            lucky_valve_idx = default_rng().choice(valve_idx, max_valve_num)
            new_row = np.zeros_like(each_row)
            new_row[lucky_valve_idx] = 1
            return new_row
        limited_rows = np.apply_along_axis(process_row, 1, over_rows)
        mask[over_rows_idx] = limited_rows
    return mask


def read_envi_ascii(file_name, save_xy=False, hdr_file_name=None):
    """
    Read envi ascii file. Use ENVI ROI Tool -> File -> output ROIs to ASCII...

    :param file_name: file name of ENVI ascii file
    :param hdr_file_name: hdr file name for a "BANDS" vector in the output
    :param save_xy: save the x, y position on the first two cols of the result vector
    :return: dict {class_name: vector, ...}
    """
    number_line_start_with = "; Number of ROIs: "
    roi_name_start_with, roi_npts_start_with = "; ROI name: ", "; ROI npts: "
    data_start_with = ";   ID"
    class_num, class_names, class_nums, vectors = 0, [], [], []
    with open(file_name, 'r') as f:
        for line_text in f:
            if line_text.startswith(number_line_start_with):
                class_num = int(line_text[len(number_line_start_with):])
            elif line_text.startswith(roi_name_start_with):
                class_names.append(line_text[len(roi_name_start_with):-1])
            elif line_text.startswith(roi_npts_start_with):
                class_nums.append(int(line_text[len(roi_name_start_with):-1]))
            elif line_text.startswith(data_start_with):
                col_list = list(filter(None, line_text[1:].split(" ")))
                assert (len(class_names) == class_num) and (len(class_names) == len(class_nums))
                break
            elif line_text.startswith(";"):
                continue
        for vector_rows in class_nums:
            vector_str = ''
            for i in range(vector_rows):
                vector_str += f.readline()
            vector = np.fromstring(vector_str, dtype=np.float, sep=" ").reshape(-1, len(col_list))
            assert vector.shape[0] == vector_rows
            vector = vector[:, 3:] if not save_xy else vector[:, 1:]
            vectors.append(vector)
            f.readline()  # suppose to read a blank line
    if hdr_file_name is not None:
        bands = []
        with open(hdr_file_name, 'r') as f:
            start_bands = False
            for line_text in f:
                if start_bands:
                    if line_text.endswith(",\n"):
                        bands.append(float(line_text[:-2]))
                    else:
                        bands.append(float(line_text))
                        break
                elif line_text.startswith("wavelength ="):
                    start_bands = True
        bands = np.array(bands, dtype=np.float)
        vectors.append(bands)
        class_names.append("BANDS")
    return dict(zip(class_names, vectors))


def generate_hdr(des='File Imported into ENVI.'):
    template_file = f"""ENVI
description = {{ {des}
  }}
samples = {Config.nCols}
lines   = {Config.nRows}
bands   = {Config.nBands}
header offset = 0
file type = ENVI Standard
data type = 4
interleave = bil
sensor type = Unknown
byte order = 0
wavelength units = Unknown
"""
    return template_file


def valve_log(log_path: pathlib.Path, valve_num: [int, str]):
    """
    将喷阀的开启次数记录到文件log_path当中。
    """
    valve_str = "截至 " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + f' 喷阀使用次数: {valve_num}.'
    with open(log_path, "a") as f:
        f.write(str(valve_str) + "\n")


if __name__ == '__main__':
    # color_dict = {(0, 0, 255): "yangeng", (255, 0, 0): "bejing", (0, 255, 0): "hongdianxian",
    #               (255, 0, 255): "chengsebangbangtang", (0, 255, 255): "lvdianxian"}
    # dataset = read_labeled_img("data/dataset", color_dict=color_dict, is_ps_color_space=False)
    # lab_scatter(dataset, class_max_num=20000, is_3d=False, is_ps_color_space=False)
    a = np.array([[1, 1, 0, 0, 1, 0, 0, 1], [0, 0, 1, 0, 0, 1, 1, 1]]).astype(np.uint8)
    # a.repeat(3, axis=0)
    # b = valve_merge(a, 2)
    # print(b)
    c = valve_expend(a)
    print(c)
