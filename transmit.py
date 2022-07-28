import os
import threading
from utils import ImgQueue as Queue
import numpy as np
from config import Config
from models import SpecDetector, RgbDetector
import typing


class Transmitter(object):
    def __init__(self):
        self.output = None

    def set_source(self, *args, **kwargs):
        """
        用于设置数据的来源，每个receiver仅允许有单个来源
        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError

    def set_output(self, output: Queue):
        """
        设置单个输出源
        :param output:
        :return:
        """
        self.output = output

    def start(self, *args, **kwargs):
        """
        启动接收线程或进程
        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError

    def stop(self, *args, **kwargs):
        """
        停止接收线程或进程
        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError


class PostProcessMethods:
    @classmethod
    def spec_data_post_process(cls, data):
        if len(data) < 3:
            threshold = int(float(data))
            print("[INFO] Get Spec threshold: ", threshold)
            return threshold
        else:
            spec_img = np.frombuffer(data, dtype=np.float32).\
                reshape((Config.nRows, Config.nBands, -1)).transpose(0, 2, 1)
            return spec_img

    @classmethod
    def rgb_data_post_process(cls, data):
        if len(data) < 3:
            threshold = int(float(data))
            print("[INFO] Get RGB threshold: ", threshold)
            return threshold
        else:
            rgb_img = np.frombuffer(data, dtype=np.uint8).reshape((Config.nRgbRows, Config.nRgbCols, -1))
            return rgb_img


class FifoReceiver(Transmitter):
    def __init__(self, fifo_path: str, output: Queue, read_max_num: int, msg_queue=None):
        super().__init__()
        self._input_fifo_path = None
        self._output_queue = None
        self._msg_queue = msg_queue
        self._max_len = read_max_num

        self.set_source(fifo_path)
        self.set_output(output)
        self._need_stop = threading.Event()
        self._need_stop.clear()
        self._running_thread = None

    def set_source(self, fifo_path: str):
        if not os.access(fifo_path, os.F_OK):
            os.mkfifo(fifo_path, 0o777)
        self._input_fifo_path = fifo_path

    def set_output(self, output: Queue):
        self._output_queue = output

    def start(self, post_process_func=None, name='fifo_receiver'):
        self._running_thread = threading.Thread(target=self._receive_thread_func,
                                                name=name, args=(post_process_func, ))
        self._running_thread.start()

    def stop(self):
        self._need_stop.set()

    def _receive_thread_func(self, post_process_func=None):
        """
        接收线程

        :param post_process_func:
        :return:
        """
        while not self._need_stop.is_set():
            input_fifo = os.open(self._input_fifo_path, os.O_RDONLY)
            data = os.read(input_fifo, self._max_len)
            if post_process_func is not None:
                data = post_process_func(data)
            if not self._output_queue.safe_put(data):
                if self._msg_queue is not None:
                    self._msg_queue.put('Fifo Receiver的接收者未来得及接收')
            os.close(input_fifo)
        self._need_stop.clear()


class FifoSender(Transmitter):
    def __init__(self, output_fifo_path: str, source: Queue):
        super().__init__()
        self._input_source = None
        self._output_fifo_path = None
        self.set_source(source)
        self.set_output(output_fifo_path)
        self._need_stop = threading.Event()
        self._need_stop.clear()
        self._running_thread = None

    def set_source(self, source: Queue):
        self._input_source = source

    def set_output(self, output_fifo_path: str):
        if not os.access(output_fifo_path, os.F_OK):
            os.mkfifo(output_fifo_path, 0o777)
        self._output_fifo_path = output_fifo_path

    def start(self, pre_process=None, name='fifo_receiver'):
        self._running_thread = threading.Thread(target=self._send_thread_func, name=name,
                                                args=(pre_process, ))
        self._running_thread.start()

    def stop(self):
        self._need_stop.set()

    def _send_thread_func(self, pre_process=None):
        """
        接收线程

        :param pre_process:
        :return:
        """
        while not self._need_stop.is_set():
            output_fifo = os.open(self._output_fifo_path, os.O_WRONLY)
            if self._input_source.empty():
                continue
            data = self._input_source.get()
            if pre_process is not None:
                data = pre_process(data)
            os.write(output_fifo, data)
            os.close(output_fifo)
        self._need_stop.clear()

    @staticmethod
    def mask_preprocess(mask: np.ndarray):
        return mask.tobytes()

    def __del__(self):
        self.stop()
        if self._running_thread is not None:
            self._running_thread.join()


class CmdImgSplitMidware(Transmitter):
    """
    用于控制命令和图像的中间件
    """
    def __init__(self, subscribers: typing.Dict[str, Queue], rgb_queue: Queue, spec_queue: Queue):
        super().__init__()
        self._rgb_queue = None
        self._spec_queue = None
        self._subscribers = None
        self._server_thread = None
        self.set_source(rgb_queue, spec_queue)
        self.set_output(subscribers)
        self.thread_stop = threading.Event()

    def set_source(self, rgb_queue: Queue, spec_queue: Queue):
        self._rgb_queue = rgb_queue
        self._spec_queue = spec_queue

    def set_output(self, output: typing.Dict[str, Queue]):
        self._subscribers = output

    def start(self, name='CMD_thread'):
        self._server_thread = threading.Thread(target=self._cmd_control_service)
        self._server_thread.start()

    def stop(self):
        self.thread_stop.set()

    def _cmd_control_service(self):
        while not self.thread_stop.is_set():
            # 判断是否有数据，如果没有数据那么就等下次吧，如果有数据来，必须保证同时
            if self._rgb_queue.empty() or self._spec_queue.empty():
                continue
            rgb_data = self._rgb_queue.get()
            spec_data = self._spec_queue.get()
            if isinstance(rgb_data, int) and isinstance(spec_data, int):
                # 看是不是命令需要执行如果是命令，就执行
                Config.rgb_size_threshold = rgb_data
                Config.spec_size_threshold = spec_data
                continue
            elif isinstance(spec_data, np.ndarray) and isinstance(rgb_data, np.ndarray):
                # 如果是图片，交给预测的人
                for _, subscriber in self._subscribers.items():
                    subscriber.put((spec_data, rgb_data))
            else:
                # 否则程序出现毁灭性问题，立刻崩
                raise Exception("两个相机传回的数据没有对上")
        self.thread_stop.clear()


class ImageSaver(Transmitter):
    """
    进行图片存储的中间件
    """
    def set_source(self, *args, **kwargs):
        pass

    def start(self, *args, **kwargs):
        pass

    def stop(self, *args, **kwargs):
        pass


class ThreadDetector(Transmitter):
    def __init__(self, input_queue: Queue, output_queue: Queue):
        super().__init__()
        self._input_queue, self._output_queue = input_queue, output_queue
        self._spec_detector = SpecDetector(blk_model_path=Config.blk_model_path,
                                           pixel_model_path=Config.pixel_model_path)
        self._rgb_detector = RgbDetector(tobacco_model_path=Config.rgb_tobacco_model_path,
                                         background_model_path=Config.rgb_background_model_path)
        self._predict_thread = None
        self._thread_exit = threading.Event()

    def set_source(self, img_queue: Queue):
        self._input_queue = img_queue

    def stop(self, *args, **kwargs):
        self._thread_exit.set()

    def start(self, name='predict_thread'):
        self._predict_thread = threading.Thread(target=self._predict_server, name=name)
        self._predict_thread.start()

    def predict(self, spec: np.ndarray, rgb: np.ndarray):
        mask = self._spec_detector.predict(spec)
        # rgb识别
        mask_rgb = self._rgb_detector.predict(rgb)
        # 结果合并
        mask_result = (mask | mask_rgb).astype(np.uint8)
        mask_result = mask_result.repeat(Config.blk_size, axis=0).repeat(Config.blk_size, axis=1).astype(np.uint8)
        return mask_result

    def _predict_server(self):
        while not self._thread_exit.is_set():
            if not self._input_queue.empty():
                spec, rgb = self._input_queue.get()
                mask = self.predict(spec, rgb)
                self._output_queue.put(mask)
        self._thread_exit.clear()
