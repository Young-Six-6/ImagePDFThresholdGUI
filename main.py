import tkinter as tk
from tkinter import filedialog, Scale, HORIZONTAL, messagebox, Toplevel
from tkinter import ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk
import cv2
import numpy as np
import os
from pdf2image import convert_from_path
import glob
import threading
import shutil  # 新增：用于创建文件夹


class ProgressWindow(Toplevel):
    """进度显示窗口"""

    def __init__(self, parent, total, title="处理中"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x100")
        self.transient(parent)  # 设置为主窗口的子窗口
        self.grab_set()  # 模态窗口，阻止操作主窗口

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self,
            variable=self.progress_var,
            maximum=total,
            length=350,
            mode='determinate'
        )
        self.progress_bar.pack(pady=10, padx=10)

        # 状态标签
        self.status_label = tk.Label(self, text="准备开始...")
        self.status_label.pack(pady=5)

        self.current = 0

    def update_progress(self, value, status=""):
        """更新进度"""
        self.current = value
        self.progress_var.set(value)
        if status:
            self.status_label.config(text=status)
        self.update_idletasks()  # 强制更新UI

    def close(self):
        """关闭进度窗口"""
        self.destroy()


class ImageViewer(Toplevel):
    """用于显示放大图像的窗口"""

    def __init__(self, parent, image, title="放大视图"):
        super().__init__(parent)
        self.title(title)
        self.geometry("800x600")
        self.resizable(True, True)

        # 创建画布和滚动条
        self.canvas = tk.Canvas(self, bg="gray")
        self.v_scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scrollbar = tk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        # 布局
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 显示图像
        self.display_image(image)

        # 绑定鼠标滚轮事件
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<Button-4>", self.zoom)  # Linux 向上滚动
        self.canvas.bind("<Button-5>", self.zoom)  # Linux 向下滚动

    def display_image(self, image):
        # 转换图像格式
        if isinstance(image, np.ndarray):
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)

        self.original_image = image
        self.image_tk = ImageTk.PhotoImage(image)

        # 更新画布
        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def zoom(self, event):
        # 缩放功能
        scale = 1.0
        if event.num == 5 or event.delta == -120:  # 缩小
            scale = 0.9
        if event.num == 4 or event.delta == 120:  # 放大
            scale = 1.1

        # 获取当前画布尺寸
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        # 缩放图像
        width, height = self.original_image.size
        new_width = int(width * scale)
        new_height = int(height * scale)

        if new_width < 50 or new_height < 50:  # 最小尺寸限制
            return

        resized_image = self.original_image.resize((new_width, new_height), Image.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(resized_image)

        # 更新画布
        self.canvas.delete("all")
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        # 调整滚动位置以保持缩放中心
        self.canvas.scale("all", x, y, scale, scale)


class ThresholdGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("图像阈值处理工具 - 保留白色")

        # 初始化变量
        self.original_image = None
        self.processed_image = None
        self.threshold_value = 200  # 默认阈值
        self.pdf_pages = []  # 存储PDF的所有页面
        self.current_pdf_page = 0  # 当前显示的PDF页码（从0开始）
        #拖拽支持
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.drop_file)
        # 创建界面组件
        self.create_widgets()

    def drop_file(self, event):
        """拖拽文件处理"""
        file_path = event.data.strip("{}")  # 去掉路径两侧的大括号
        if os.path.isfile(file_path):
            if file_path.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tif')):
                try:
                    if file_path.lower().endswith('.pdf'):
                        threading.Thread(target=self.handle_pdf_thread, args=(file_path,), daemon=True).start()
                    else:
                        self.original_image = cv2.imread(file_path)
                        if self.original_image is None:
                            raise ValueError("无法读取图像文件")
                        self.gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
                        self.display_original_image()
                        self.process_image()
                        self.pdf_pages = []
                        self.page_label.config(text="")
                        self.prev_btn.config(state=tk.DISABLED)
                        self.next_btn.config(state=tk.DISABLED)
                    self.save_btn.config(state=tk.NORMAL)
                    self.batch_btn.config(state=tk.NORMAL)
                except Exception as e:
                    messagebox.showerror("错误", f"无法打开文件: {str(e)}")
            else:
                messagebox.showwarning("不支持的文件", "请拖入图片或 PDF 文件")
    def create_widgets(self):
        # 顶部框架 - 按钮区域
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10)

        # 打开图片按钮（支持PDF）
        self.open_btn = tk.Button(top_frame, text="打开图片/PDF", command=self.open_file)
        self.open_btn.pack(side=tk.LEFT, padx=5)

        # 保存图片按钮
        self.save_btn = tk.Button(top_frame, text="保存结果", command=self.save_image, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)

        # 批量处理按钮
        self.batch_btn = tk.Button(top_frame, text="批量处理", command=self.batch_process, state=tk.DISABLED)
        self.batch_btn.pack(side=tk.LEFT, padx=5)

        # 阈值滑块
        slider_frame = tk.Frame(self.root)
        slider_frame.pack(pady=10)

        tk.Label(slider_frame, text="阈值:").pack(side=tk.LEFT)
        self.threshold_slider = Scale(
            slider_frame,
            from_=0,
            to=255,
            orient=HORIZONTAL,
            length=400,
            command=self.update_threshold
        )
        self.threshold_slider.set(self.threshold_value)
        self.threshold_slider.pack(side=tk.LEFT, padx=5)

        # 阈值值显示
        self.value_label = tk.Label(slider_frame, text=str(self.threshold_value))
        self.value_label.pack(side=tk.LEFT, padx=5)

        # PDF页面导航组件
        self.nav_frame = tk.Frame(self.root)
        self.nav_frame.pack(pady=5)

        self.prev_btn = tk.Button(self.nav_frame, text="上一页", command=self.prev_pdf_page, state=tk.DISABLED)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.page_label = tk.Label(self.nav_frame, text="")  # 显示当前页码/总页数
        self.page_label.pack(side=tk.LEFT, padx=5)

        self.next_btn = tk.Button(self.nav_frame, text="下一页", command=self.next_pdf_page, state=tk.DISABLED)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # 说明文本
        info_label = tk.Label(self.root, text="高阈值保留更多白色，低阈值保留较少白色", fg="blue")
        info_label.pack(pady=5)
        info_label = tk.Label(self.root, text="支持拖拽打开", fg="gray")
        info_label.pack(pady=5)

        # 批量处理说明
        batch_info = tk.Label(self.root, text="批量处理: 处理当前目录input文件夹中所有图片和PDF，结果保存到output文件夹",
                              fg="green")
        batch_info.pack(pady=5)

        # 图像显示区域
        self.image_frame = tk.Frame(self.root)
        self.image_frame.pack(pady=10)

        # 原图标签
        self.original_label = tk.Label(self.image_frame, text="原图 (双击放大)")
        self.original_label.grid(row=0, column=0, padx=10)

        # 处理后的图标签
        self.processed_label = tk.Label(self.image_frame, text="处理后 (保留白色, 双击放大)")
        self.processed_label.grid(row=0, column=1, padx=10)

        # 图像显示区域
        self.original_canvas = tk.Canvas(self.image_frame, width=400, height=400, bg="gray")
        self.original_canvas.grid(row=1, column=0, padx=10, pady=10)
        self.original_canvas.bind("<Double-Button-1>", self.zoom_original)

        self.processed_canvas = tk.Canvas(self.image_frame, width=400, height=400, bg="gray")
        self.processed_canvas.grid(row=1, column=1, padx=10, pady=10)
        self.processed_canvas.bind("<Double-Button-1>", self.zoom_processed)

    def open_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tif"),
                ("PDF files", "*.pdf")
            ]
        )

        if file_path:
            try:
                if file_path.lower().endswith('.pdf'):
                    # 启动线程处理PDF，避免UI卡顿
                    threading.Thread(target=self.handle_pdf_thread, args=(file_path,), daemon=True).start()
                else:
                    self.original_image = cv2.imread(file_path)
                    if self.original_image is None:
                        raise ValueError("无法读取图像文件")
                    self.gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
                    self.display_original_image()
                    self.process_image()
                    # 重置PDF相关状态
                    self.pdf_pages = []
                    self.page_label.config(text="")
                    self.prev_btn.config(state=tk.DISABLED)
                    self.next_btn.config(state=tk.DISABLED)

                self.save_btn.config(state=tk.NORMAL)
                self.batch_btn.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件: {str(e)}")

    def handle_pdf_thread(self, file_path):
        """在线程中处理PDF，避免UI卡顿"""
        try:
            # 获取PDF总页数
            total_pages = len(convert_from_path(file_path))
            if total_pages == 0:
                raise ValueError("无法从PDF中提取页面")

            # 在主线程中创建进度窗口
            self.root.after(0, lambda: self.create_pdf_progress_window(total_pages, file_path))

            # 转换PDF页面
            self.pdf_pages = []
            for i in range(total_pages):
                # 转换单页
                page = convert_from_path(file_path, first_page=i + 1, last_page=i + 1)[0]
                open_cv_image = np.array(page)
                bgr_image = open_cv_image[:, :, ::-1].copy()  # RGB转BGR
                self.pdf_pages.append(bgr_image)

                # 更新进度
                progress = i + 1
                status = f"正在处理第 {progress}/{total_pages} 页..."
                self.root.after(0, lambda p=progress, s=status: self.update_pdf_progress(p, s))

            # 处理完成后显示第一页
            self.root.after(0, self.finish_pdf_handling)

        except Exception as e:
            error_msg = f"处理PDF时出错: {str(e)}\n请确保已安装poppler并配置环境变量"
            self.root.after(0, lambda: messagebox.showerror("PDF处理错误", error_msg))
            self.root.after(0, self.close_pdf_progress_window)

    def create_pdf_progress_window(self, total, file_path):
        """创建PDF处理进度窗口"""
        filename = os.path.basename(file_path)
        self.pdf_progress_window = ProgressWindow(self.root, total, f"处理PDF: {filename}")

    def update_pdf_progress(self, value, status):
        """更新PDF处理进度"""
        if hasattr(self, 'pdf_progress_window'):
            self.pdf_progress_window.update_progress(value, status)

    def close_pdf_progress_window(self):
        """关闭PDF进度窗口"""
        if hasattr(self, 'pdf_progress_window'):
            self.pdf_progress_window.close()
            delattr(self, 'pdf_progress_window')

    def finish_pdf_handling(self):
        """完成PDF处理后显示第一页并初始化导航"""
        self.close_pdf_progress_window()
        if self.pdf_pages:
            self.current_pdf_page = 0  # 重置为第一页
            self.original_image = self.pdf_pages[self.current_pdf_page]
            self.gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            self.display_original_image()
            self.process_image()
            # 启用导航按钮并更新页码显示
            self.prev_btn.config(state=tk.DISABLED)  # 第一页禁用上一页
            self.next_btn.config(state=tk.NORMAL if len(self.pdf_pages) > 1 else tk.DISABLED)
            self.page_label.config(text=f"第 {self.current_pdf_page + 1}/{len(self.pdf_pages)} 页")

    def prev_pdf_page(self):
        """切换到上一页PDF"""
        if self.pdf_pages and self.current_pdf_page > 0:
            self.current_pdf_page -= 1
            self.update_pdf_display()

    def next_pdf_page(self):
        """切换到下一页PDF"""
        if self.pdf_pages and self.current_pdf_page < len(self.pdf_pages) - 1:
            self.current_pdf_page += 1
            self.update_pdf_display()

    def update_pdf_display(self):
        """更新当前PDF页面的显示"""
        if not self.pdf_pages:
            return
        # 更新当前页面图像
        self.original_image = self.pdf_pages[self.current_pdf_page]
        self.gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
        self.display_original_image()
        self.process_image()  # 重新处理当前页
        # 更新页码显示
        self.page_label.config(text=f"第 {self.current_pdf_page + 1}/{len(self.pdf_pages)} 页")
        # 控制导航按钮状态
        self.prev_btn.config(state=tk.NORMAL if self.current_pdf_page > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.current_pdf_page < len(self.pdf_pages) - 1 else tk.DISABLED)

    def display_original_image(self):
        # 保存原始图像用于放大
        self.original_image_for_display = self.original_image.copy()

        # 调整图像大小以适应画布
        height, width = self.original_image.shape[:2]
        max_size = 400
        if height > max_size or width > max_size:
            scale = max_size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            display_image = cv2.resize(self.original_image, (new_width, new_height))
        else:
            display_image = self.original_image

        # 转换颜色空间从BGR到RGB
        display_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)

        # 转换为PIL图像格式
        pil_image = Image.fromarray(display_image)

        # 转换为Tkinter可用的图像格式
        self.original_photo = ImageTk.PhotoImage(pil_image)

        # 在画布上显示图像
        self.original_canvas.delete("all")
        self.original_canvas.create_image(
            200, 200, anchor=tk.CENTER, image=self.original_photo
        )

    def process_image(self):
        # 应用阈值处理 - 保留白色
        _, self.processed_image = cv2.threshold(
            self.gray_image,
            self.threshold_value,
            255,
            cv2.THRESH_BINARY
        )

        # 保存处理后的图像用于放大
        self.processed_image_for_display = self.processed_image.copy()

        # 显示处理后的图像
        self.display_processed_image()

    def display_processed_image(self):
        if self.processed_image is None:
            return

        # 调整图像大小以适应画布
        height, width = self.processed_image.shape[:2]
        max_size = 400
        if height > max_size or width > max_size:
            scale = max_size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            display_image = cv2.resize(self.processed_image, (new_width, new_height))
        else:
            display_image = self.processed_image

        # 转换为PIL图像格式
        pil_image = Image.fromarray(display_image)

        # 转换为Tkinter可用的图像格式
        self.processed_photo = ImageTk.PhotoImage(pil_image)

        # 在画布上显示图像
        self.processed_canvas.delete("all")
        self.processed_canvas.create_image(
            200, 200, anchor=tk.CENTER, image=self.processed_photo
        )

    def update_threshold(self, value):
        self.threshold_value = int(value)
        self.value_label.config(text=str(self.threshold_value))

        if self.original_image is not None:
            self.process_image()

    def save_image(self):
        if self.processed_image is None:
            return

        # 判断是否为PDF文件
        is_pdf = bool(self.pdf_pages)

        if is_pdf:
            # 询问用户保存当前页还是全部页
            choice = messagebox.askyesnocancel(
                "保存选项",
                f"检测到这是一个多页PDF（共{len(self.pdf_pages)}页）\n"
                "是否保存全部页面？\n"
                "【是】保存全部页 | 【否】仅保存当前页 | 【取消】取消保存"
            )
            if choice is None:  # 取消
                return
            save_all = choice
        else:
            save_all = False

        if save_all:
            # 保存全部PDF页面
            save_dir = filedialog.askdirectory(title="选择保存目录")
            if not save_dir:
                return
            # 遍历所有页面，处理并保存
            for i, page in enumerate(self.pdf_pages):
                # 处理当前页
                gray_img = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
                _, processed_img = cv2.threshold(gray_img, self.threshold_value, 255, cv2.THRESH_BINARY)
                # 生成文件名（带页码）
                filename = f"pdf_page_{i + 1}.png"
                save_path = os.path.join(save_dir, filename)
                # 解决中文路径问题
                cv2.imencode('.png', processed_img)[1].tofile(save_path)
            messagebox.showinfo("保存成功", f"全部{len(self.pdf_pages)}页已保存至：\n{save_dir}")
        else:
            # 保存当前页
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
            )
            if file_path:
                # 解决中文路径问题
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg']:
                    cv2.imencode('.jpg', self.processed_image)[1].tofile(file_path)
                else:
                    cv2.imencode('.png', self.processed_image)[1].tofile(file_path)
                messagebox.showinfo("保存成功", f"图像已保存至: {file_path}")

    def zoom_original(self, event):
        """双击原图放大"""
        if hasattr(self, 'original_image_for_display'):
            viewer = ImageViewer(self.root, self.original_image_for_display, "原图放大视图")

    def zoom_processed(self, event):
        """双击处理后的图放大"""
        if hasattr(self, 'processed_image_for_display'):
            viewer = ImageViewer(self.root, self.processed_image_for_display, "处理后图像放大视图")

    def batch_process(self):
        """批量处理input文件夹中的所有图片和PDF"""
        input_dir = os.path.join(os.getcwd(), "input")
        output_dir = os.path.join(os.getcwd(), "output")

        if not os.path.exists(input_dir):
            os.makedirs(input_dir)
            messagebox.showinfo("提示", f"已创建input文件夹，请将需要处理的文件放入 {input_dir}")
            return

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 支持的文件格式（包括图片和PDF）
        all_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tif', '*.pdf']
        all_files = []

        for ext in all_extensions:
            all_files.extend(glob.glob(os.path.join(input_dir, ext)))

        if not all_files:
            messagebox.showinfo("提示", "input文件夹中没有找到支持的文件（图片或PDF）")
            return

        # 计算总任务量（图片1页，PDF计算实际页数）
        total_tasks = 0
        file_tasks = []  # 存储每个文件的任务量

        for file_path in all_files:
            if file_path.lower().endswith('.pdf'):
                try:
                    page_count = len(convert_from_path(file_path))
                    total_tasks += page_count
                    file_tasks.append((file_path, page_count))
                except:
                    file_tasks.append((file_path, 0))  # 标记为错误文件
            else:
                total_tasks += 1
                file_tasks.append((file_path, 1))

        if total_tasks == 0:
            messagebox.showinfo("提示", "没有可处理的有效文件")
            return

        # 启动线程处理批量任务
        threading.Thread(
            target=self.batch_process_thread,
            args=(file_tasks, output_dir, total_tasks),
            daemon=True
        ).start()

    def batch_process_thread(self, file_tasks, output_dir, total_tasks):
        """批量处理线程"""
        # 在主线程创建进度窗口
        self.root.after(0, lambda: self.create_batch_progress_window(total_tasks))

        current_task = 0
        processed_count = 0

        for file_path, page_count in file_tasks:
            try:
                filename = os.path.splitext(os.path.basename(file_path))[0]

                if file_path.lower().endswith('.pdf') and page_count > 0:
                    # 处理PDF文件 - 新增：创建对应文件夹
                    pdf_output_dir = os.path.join(output_dir, filename)
                    os.makedirs(pdf_output_dir, exist_ok=True)

                    pages = convert_from_path(file_path)
                    for i, page in enumerate(pages, 1):
                        current_task += 1
                        status = f"处理PDF: {filename} (第{i}/{page_count}页)"
                        self.root.after(0, lambda c=current_task, s=status: self.update_batch_progress(c, s))

                        # 转换为OpenCV格式并处理
                        open_cv_image = np.array(page)
                        img = open_cv_image[:, :, ::-1].copy()  # RGB转BGR
                        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        _, processed_img = cv2.threshold(gray_img, self.threshold_value, 255, cv2.THRESH_BINARY)

                        # 保存处理结果 - 保存到PDF专属文件夹
                        output_path = os.path.join(pdf_output_dir, f"page_{i}.png")
                        # 解决中文路径问题
                        cv2.imencode('.png', processed_img)[1].tofile(output_path)
                        processed_count += 1
                elif not file_path.lower().endswith('.pdf'):
                    # 处理图片文件
                    current_task += 1
                    status = f"处理图片: {filename}"
                    self.root.after(0, lambda c=current_task, s=status: self.update_batch_progress(c, s))

                    img = cv2.imread(file_path)
                    if img is not None:
                        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        _, processed_img = cv2.threshold(gray_img, self.threshold_value, 255, cv2.THRESH_BINARY)

                        output_path = os.path.join(output_dir, os.path.basename(file_path))
                        # 解决中文路径问题
                        ext = os.path.splitext(output_path)[1].lower()
                        if ext in ['.jpg', '.jpeg']:
                            cv2.imencode('.jpg', processed_img)[1].tofile(output_path)
                        else:
                            cv2.imencode('.png', processed_img)[1].tofile(output_path)
                        processed_count += 1
            except Exception as e:
                error_msg = f"处理文件 {os.path.basename(file_path)} 时出错: {str(e)}"
                self.root.after(0, lambda m=error_msg: messagebox.showerror("处理错误", m))

        # 处理完成
        self.root.after(0, self.close_batch_progress_window)
        self.root.after(0, lambda: messagebox.showinfo(
            "完成",
            f"批量处理完成，共处理 {processed_count} 个文件/页面，结果保存在 {output_dir}"
        ))

    def create_batch_progress_window(self, total):
        """创建批量处理进度窗口"""
        self.batch_progress_window = ProgressWindow(self.root, total, "批量处理中")

    def update_batch_progress(self, value, status):
        """更新批量处理进度"""
        if hasattr(self, 'batch_progress_window'):
            self.batch_progress_window.update_progress(value, status)

    def close_batch_progress_window(self):
        """关闭批量处理进度窗口"""
        if hasattr(self, 'batch_progress_window'):
            self.batch_progress_window.close()
            delattr(self, 'batch_progress_window')


if __name__ == "__main__":
    root = TkinterDnD.Tk()  # 使用支持拖拽的Tk
    app = ThresholdGUI(root)
    root.mainloop()
