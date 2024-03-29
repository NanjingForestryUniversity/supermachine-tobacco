import os

import numpy as np


class Config:
    # 文件相关参数
    nRows, nCols, nBands = 256, 1024, 22
    nRgbRows, nRgbCols, nRgbBands = 1024, 4096, 3

    # 需要设置的谱段等参数
    selected_bands = [127, 201, 202, 294]
    bands = [127, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210,
             211, 212, 213, 214, 215, 216, 217, 218, 219, 294]
    is_yellow_min = np.array([0.10167048, 0.1644719, 0.1598884, 0.31534621])
    is_yellow_max = np.array([0.212984, 0.25896924, 0.26509268, 0.51943593])
    is_black_threshold = np.asarray([0.1369, 0.1472, 0.1439, 0.1814])
    black_yellow_bands = [0, 2, 3, 21]
    green_bands = [i for i in range(1, 21)]

    # 光谱模型参数
    blk_size = 4  # 必须是2的倍数，不然会出错
    pixel_model_path = r"./weights/pixel_2022-08-02_15-22.model"  # 开发时的路径
    # pixel_model_path = r"/home/dt/tobacco-color/weights/pixel_2022-08-02_15-22.model"  # 机器上部署的路径
    blk_model_path = r"./weights/rf_4x4_c22_20_sen8_9.model"  # 开发时的路径
    # blk_model_path = r"/home/dt/tobacco-color/weights/rf_4x4_c22_20_sen8_9.model"  # 机器上部署的路径
    spec_size_threshold = 3

    s_threshold_a = 124  # s_a的最高允许值
    s_threshold_b = 124  # s_b的最高允许值

    # rgb模型参数
    rgb_tobacco_model_path = r"weights/tobacco_dt_2022-08-27_14-43.model"  # 开发时的路径
    # rgb_tobacco_model_path = r"/home/dt/tobacco-color/weights/tobacco_dt_2022-08-27_14-43.model"  # 机器上部署的路径
    rgb_background_model_path = r"weights/background_dt_2023-12-26_20-39.model"  # 开发时的路径
    # rgb_background_model_path = r"/home/dt/tobacco-color/weights/background_dt_2022-08-22_22-15.model"  # 机器上部署的路径
    threshold_low, threshold_high = 10, 230
    threshold_s = 190  # 饱和度的最高允许值
    threshold_a = 125  # a的最高允许值
    threshold_b = 126  # b的最高允许值
    rgb_size_threshold = 6  # rgb的尺寸限制
    lab_size_threshold = 6  # lab的尺寸限制
    ai_path = 'weights/best1227.pt'  # 开发时的路径
    # ai_path = '/home/dt/tobacco-color/weights/best0827.pt'  # 机器上部署的路径
    ai_conf_threshold = 0.8

    # mask parameter
    target_size = (1024, 1024)  # (Width, Height) of mask
    valve_merge_size = 2  # 每两个喷阀当中有任意一个出现杂质则认为都是杂质
    valve_horizontal_padding = 5  # 喷阀横向膨胀的尺寸，应该是奇数,3时表示左右各膨胀1,5时表示左右各膨胀2(23.9.20老倪要求改为5)
    max_open_valve_limit = 25  # 最大同时开启喷阀限制,按照电流计算，当前的喷阀可以开启的喷阀 600W的电源 / 12V电源 = 50A, 一个阀门1A
    max_time_spent = 200
    # save part
    offset_vertical = 0

    # logging
    root_dir = os.path.split(os.path.realpath(__file__))[0]
    log_freq = 1500  # 进行log的频率（多少次predict后进行log写出记录喷阀开启次数）
    rgb_log_dir = 'rgb_log'  # rgb log 文件夹
    spec_log_dir = 'spec_log'  # spec log 文件夹
