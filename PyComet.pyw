import sys
import os
import json
import subprocess
import threading
import tempfile
import time
import platform
import base64
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


class AESHelper:
    """AES加密辅助类"""
    
    def __init__(self, key):
        """初始化AES加密器
        
        Args:
            key: 加密密钥，将使用SHA256哈希生成32字节密钥
        """
        # 使用SHA256生成32字节密钥
        from hashlib import sha256
        self.key = sha256(key.encode('utf-8')).digest()
    
    def encrypt(self, plaintext):
        """加密文本
        
        Args:
            plaintext: 明文文本
            
        Returns:
            包含IV和密文的base64编码字符串
        """
        # 生成随机IV
        iv = get_random_bytes(AES.block_size)
        
        # 创建AES加密器
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        
        # 加密数据
        ciphertext = cipher.encrypt(pad(plaintext.encode('utf-8'), AES.block_size))
        
        # 返回IV+密文的base64编码
        return base64.b64encode(iv + ciphertext).decode('utf-8')
    
    def decrypt(self, encrypted_text):
        """解密文本
        
        Args:
            encrypted_text: 包含IV和密文的base64编码字符串
            
        Returns:
            解密后的明文文本
        """
        try:
            # 解码base64
            data = base64.b64decode(encrypted_text)
            
            # 提取IV和密文
            iv = data[:AES.block_size]
            ciphertext = data[AES.block_size:]
            
            # 创建AES解密器
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            
            # 解密并去除填充
            plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
            
            return plaintext.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            return ""


class ApiKeyDialog(QDialog):
    """API密钥设置对话框"""
    # 在ApiKeyDialog类的__init__方法中，修改API密钥输入框的部分
    def __init__(self, parent=None, current_key=""):
        super().__init__(parent)
        self.setWindowTitle("设置API密钥")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 说明标签
        self.info_label = QLabel("请输入智谱AI API密钥:")
        layout.addWidget(self.info_label)
        
        # 创建API密钥输入框的布局
        api_key_layout = QHBoxLayout()
        
        # API密钥输入框
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("在此输入您的API密钥")
        self.api_key_input.setText(current_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)  # 设置为密码模式
        
        # === 新增：创建🙈按钮 ===
        self.show_password_button = QPushButton("🙈")
        self.show_password_button.setFixedSize(30, 30)
        self.show_password_button.setToolTip("显示/隐藏密码")
        self.show_password_button.clicked.connect(self.toggle_password_visibility)
        
        api_key_layout.addWidget(self.api_key_input)
        api_key_layout.addWidget(self.show_password_button)
        
        layout.addLayout(api_key_layout)
        
        # 获取API密钥的链接
        link_label = QLabel('还没有API密钥？<a href="https://open.bigmodel.cn/usercenter/apikeys">点击这里获取</a>')
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red;")
        layout.addWidget(self.status_label)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_api_key)
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        
        self.later_button = QPushButton("稍后设置")
        self.later_button.clicked.connect(lambda: self.done(1))
        button_layout.addWidget(self.later_button)
        
        self.ok_button = QPushButton("完成")
        self.ok_button.clicked.connect(lambda: self.done(0))
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        # 设置焦点
        if not current_key:
            self.api_key_input.setFocus()
        
        # 标记当前密码可见性状态
        self.password_visible = False

    def toggle_password_visibility(self):
        """切换密码可见性 - 动漫风格"""
        if self.password_visible:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.show_password_button.setText("🙈")  # 闭眼
            self.password_visible = False
        else:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.show_password_button.setText("👀")  # 睁眼
            self.password_visible = True
        
    def get_api_key(self):
        """获取API密钥"""
        return self.api_key_input.text().strip()
    
    def test_api_key(self):
        """测试API密钥是否有效"""
        api_key = self.get_api_key()
        if not api_key:
            self.status_label.setText("请输入API密钥")
            return
        
        self.status_label.setText("测试连接中...")
        self.test_button.setEnabled(False)
        self.repaint()  # 强制重绘以显示状态
        
        # 在新线程中测试连接
        def test_connection():
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                data = {
                    "model": "glm-4-flash",
                    "messages": [{"role": "user", "content": "测试连接，请回复'连接成功'"}],
                    "stream": False
                }
                
                response = requests.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.status_label.setText("连接成功！")
                    self.status_label.setStyleSheet("color: green;")
                else:
                    self.status_label.setText(f"连接失败: {response.status_code}")
                    self.status_label.setStyleSheet("color: red;")
                    
            except Exception as e:
                self.status_label.setText(f"连接错误: {str(e)}")
                self.status_label.setStyleSheet("color: red;")
            
            self.test_button.setEnabled(True)
        
        # 在新线程中执行测试
        thread = threading.Thread(target=test_connection)
        thread.daemon = True
        thread.start()


class CodeEditor(QPlainTextEdit):
    """自定义代码编辑器，支持Python语法高亮和行号"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 10))
        
        # 不在这里设置主题，由主窗口统一设置
        
        # 行号区域
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)
        
        # 初始化语法高亮
        self.highlighter = PythonHighlighter(self.document())
        
    def apply_dark_theme(self):
        """应用深色主题"""
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)
    
    def apply_light_theme(self):
        """应用浅色主题"""
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #000000;
                selection-background-color: #a8d1ff;
            }
        """)
        
    def line_number_area_width(self):
        """计算行号区域的宽度"""
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().width('9') * digits
        return space
    
    def update_line_number_area_width(self, _):
        """更新行号区域的宽度"""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """更新行号区域"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), 
                                        self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """重写resize事件"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), 
                 self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event, is_dark_theme=True):
        """绘制行号"""
        painter = QPainter(self.line_number_area)
        
        # 根据主题设置行号区域颜色
        if is_dark_theme:
            painter.fillRect(event.rect(), QColor("#252526"))
            pen_color = QColor("#858585")
        else:
            painter.fillRect(event.rect(), QColor("#f5f5f5"))
            pen_color = QColor("#666666")
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        painter.setPen(pen_color)
        painter.setFont(QFont("Consolas", 9))
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(0, int(top), self.line_number_area.width() - 3, 
                               self.fontMetrics().height(),
                               Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def indent_selection(self):
        """增加缩进：选中行或当前行前插入4个空格"""
        cursor = self.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # 获取选中的文本块
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfBlock)
            start_block = cursor.block().blockNumber()
            
            cursor.setPosition(end)
            cursor.movePosition(QTextCursor.StartOfBlock)
            end_block = cursor.block().blockNumber()
            
            # 获取所有行
            lines = self.toPlainText().split('\n')
            
            # 在每一行前插入4个空格
            for i in range(start_block, end_block + 1):
                if i < len(lines):
                    lines[i] = '    ' + lines[i]
            
            # 更新文本
            cursor.select(QTextCursor.Document)
            cursor.insertText('\n'.join(lines))
            
            # 恢复选中状态
            cursor.setPosition(self.document().findBlockByNumber(start_block).position())
            for _ in range(end_block - start_block):
                cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            # 没有选中文本，在当前行插入4个空格
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.insertText('    ')
    
    def unindent_selection(self):
        """减少缩进：选中行或当前行去掉4个空格（或尽可能多的空格）"""
        cursor = self.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # 获取选中的文本块
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfBlock)
            start_block = cursor.block().blockNumber()
            
            cursor.setPosition(end)
            cursor.movePosition(QTextCursor.StartOfBlock)
            end_block = cursor.block().blockNumber()
            
            # 获取所有行
            lines = self.toPlainText().split('\n')
            
            # 在每一行去掉4个空格（如果行首有4个空格）或尽可能多的空格
            for i in range(start_block, end_block + 1):
                if i < len(lines):
                    # 去掉行首的空格，最多4个
                    space_count = 0
                    for ch in lines[i][:4]:
                        if ch == ' ':
                            space_count += 1
                        else:
                            break
                    if space_count > 0:
                        lines[i] = lines[i][space_count:]
            
            # 更新文本
            cursor.select(QTextCursor.Document)
            cursor.insertText('\n'.join(lines))
            
            # 恢复选中状态
            cursor.setPosition(self.document().findBlockByNumber(start_block).position())
            for _ in range(end_block - start_block):
                cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            self.setTextCursor(cursor)
        else:
            # 没有选中文本，在当前行去掉4个空格（如果行首有4个空格）或尽可能多的空格
            cursor.movePosition(QTextCursor.StartOfBlock)
            line_text = cursor.block().text()
            # 计算行首空格数
            space_count = 0
            for ch in line_text[:4]:
                if ch == ' ':
                    space_count += 1
                else:
                    break
            if space_count > 0:
                # 删除空格
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, space_count)
                cursor.removeSelectedText()
    
    def keyPressEvent(self, event):
        """处理键盘事件，特别是Tab、Ctrl+Tab和自动缩进"""
        if event.key() == Qt.Key_Tab:
            if event.modifiers() & Qt.ControlModifier:  # Ctrl+Tab 减少缩进
                self.unindent_selection()
            else:  # Tab 增加缩进
                self.indent_selection()
        elif event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            # Ctrl+Enter 运行代码
            self.parent().run_code()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 处理回车键，实现自动缩进
            cursor = self.textCursor()
            
            # 保存当前光标位置
            current_pos = cursor.position()
            
            # 移动到当前行的开始，然后选中到行首，获取当前行的缩进
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            current_line_text = cursor.selectedText()
            
            # 将光标恢复到原始位置
            cursor.setPosition(current_pos)
            
            # 计算当前行的缩进（空格数量）
            indent_count = 0
            for ch in current_line_text:
                if ch == ' ':
                    indent_count += 1
                else:
                    break
            
            # 检查上一行是否以冒号结尾
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.Up)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            prev_line_text = cursor.selectedText().rstrip()  # 去除行尾空白
            
            # 恢复光标到准备插入新行的位置
            cursor.setPosition(current_pos)
            # 插入换行符（这会触发父类的默认换行行为）
            super().keyPressEvent(event)
            
            # 现在光标在新行的开头，为其设置缩进
            if prev_line_text.endswith(':'):
                # 以冒号结尾，增加一级缩进
                cursor.insertText(' ' * (indent_count + 4))
            else:
                # 不是以冒号结尾，保持相同缩进
                cursor.insertText(' ' * indent_count)
        else:
            # 其他按键交给父类处理
            super().keyPressEvent(event)


class LineNumberArea(QWidget):
    """行号区域部件"""
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
        self.is_dark_theme = True  # 默认深色主题
    
    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event, self.is_dark_theme)


class PythonHighlighter(QSyntaxHighlighter):
    """Python语法高亮器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 定义高亮规则
        self.highlighting_rules = []
        
        # 关键字
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'True', 'try', 'while', 'with', 'yield'
        ]
        
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Bold)
        
        for word in keywords:
            pattern = r'\b' + word + r'\b'
            rule = (QRegExp(pattern), keyword_format)
            self.highlighting_rules.append(rule)
        
        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self.highlighting_rules.append((QRegExp(r'\".*\"'), string_format))
        self.highlighting_rules.append((QRegExp(r'\'.*\''), string_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self.highlighting_rules.append((QRegExp(r'\b[0-9]+\b'), number_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self.highlighting_rules.append((QRegExp(r'#.*'), comment_format))
        
        # 函数
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#dcdcaa"))
        self.highlighting_rules.append((QRegExp(r'\b[A-Za-z0-9_]+(?=\()'), function_format))
    
    def highlightBlock(self, text):
        """应用高亮规则"""
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)


class CometIDE(QMainWindow):
    """彗星IDE主窗口"""
    
    # 定义信号用于线程间通信
    console_update_signal = pyqtSignal(str, str)  # 第二个参数表示颜色
    comet_response_signal = pyqtSignal(str)
    comet_error_signal = pyqtSignal(str)
    request_finished_signal = pyqtSignal()
    process_finished_signal = pyqtSignal()  # 新增：进程完成信号
    
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"  # 当前主题，默认为深色
        self.current_running_code = ""  # 保存当前运行的代码
        self.is_fix_mode = False  # 是否为修复模式
        self.has_error = False  # 标记是否有错误信息
        self.input_process = None  # 交互式执行的子进程
        self.input_thread = None  # 读取输出的线程
        self.is_running = False  # 标记是否有进程正在运行
        self.non_interactive_process = None  # 非交互式执行的进程
        
        # 初始化AES加密器
        self.aes_helper = AESHelper("zy142857")
        
        # 加载API密钥配置
        self.api_key = self.load_api_key()
        
        # 如果没有API密钥或密钥无效，提示用户设置
        if not self.api_key or not self.test_api_key(self.api_key):
            self.show_api_key_dialog()
        
        # 先创建UI部件
        self.init_ui()
        
        # 然后创建共享的action
        self.create_shared_actions()
        
        # 最后创建菜单
        self.create_menu()
        
        self.init_shortcuts()
        self.init_auto_save()
        self.load_autosave()
        
        # 连接信号
        self.console_update_signal.connect(self.update_console)
        self.comet_response_signal.connect(self.update_comet_response)
        self.comet_error_signal.connect(self.update_comet_error)
        self.request_finished_signal.connect(self.enable_send_button)
        self.process_finished_signal.connect(self.on_process_finished)  # 新增
    
    def load_api_key(self):
        """从配置文件加载API密钥（支持加密和明文格式）"""
        config_file = "comet_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # 首先尝试加载加密的API密钥
                    if 'api_key_encrypted' in config:
                        encrypted_key = config.get('api_key_encrypted', '')
                        if encrypted_key:
                            # 解密API密钥
                            decrypted_key = self.aes_helper.decrypt(encrypted_key)
                            if decrypted_key:
                                return decrypted_key
                    
                    # 如果没有加密的密钥，尝试加载明文的（兼容旧版本）
                    elif 'api_key' in config:
                        plain_key = config.get('api_key', '').strip()
                        if plain_key:
                            # 将明文密钥加密保存
                            self.save_api_key(plain_key)
                            return plain_key
                    
            except Exception as e:
                print(f"读取配置文件失败: {e}")
        
        return ""
    
    def save_api_key(self, api_key):
        """加密并保存API密钥到配置文件"""
        config_file = "comet_config.json"
        
        try:
            # 加密API密钥
            encrypted_key = self.aes_helper.encrypt(api_key)
            
            # 创建配置
            config = {
                'api_key_encrypted': encrypted_key,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 如果配置文件已存在，读取现有配置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
                    # 移除可能存在的明文API密钥
                    if 'api_key' in existing_config:
                        del existing_config['api_key']
                    # 更新配置
                    existing_config.update(config)
                    config = existing_config
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def test_api_key(self, api_key):
        """测试API密钥是否有效"""
        if not api_key:
            return False
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            data = {
                "model": "glm-4-flash",
                "messages": [{"role": "user", "content": "测试连接，请回复'连接成功'"}],
                "stream": False
            }
            
            response = requests.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=data,
                timeout=5
            )
            
            return response.status_code == 200
        except:
            return False
    
    def show_api_key_dialog(self):
        """显示API密钥设置对话框"""
        while True:
            dialog = ApiKeyDialog(self, self.api_key)
            result = dialog.exec_()
            
            if result == 0:  # 用户点击"完成"
                new_api_key = dialog.get_api_key()
                
                if not new_api_key:
                    QMessageBox.warning(self, "输入为空", "请输入API密钥")
                    continue
                
                # 测试新的API密钥
                if self.test_api_key(new_api_key):
                    # 保存API密钥
                    if self.save_api_key(new_api_key):
                        self.api_key = new_api_key
                        QMessageBox.information(self, "成功", "API密钥设置成功！")
                        break
                    else:
                        QMessageBox.warning(self, "保存失败", "保存API密钥失败，请检查配置文件权限")
                else:
                    QMessageBox.warning(self, "连接失败", "API密钥无效，请重新输入")
            else:  # 用户点击"稍后设置"
                if not self.api_key:
                    QMessageBox.warning(self, "注意", "没有有效的API密钥，Comet功能将无法使用。\n您可以在菜单栏的'设置'中随时设置API密钥。")
                break
    
    def set_api_key(self):
        """设置API密钥（菜单调用）"""
        self.show_api_key_dialog()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("PyComet")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建水平布局用于三个主要面板
        h_splitter = QSplitter(Qt.Horizontal)
        
        # 1. 编辑面板 (左侧)
        self.editor_panel = CodeEditor(self)
        h_splitter.addWidget(self.editor_panel)
        
        # 创建垂直分割器用于右侧的两个面板
        v_splitter = QSplitter(Qt.Vertical)
        
        # 2. 控制台面板 (右下) - 添加标题和修复按钮
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)
        
        # 控制台标题栏 - 包含标题和修复按钮
        console_title_bar = QWidget()
        console_title_layout = QHBoxLayout(console_title_bar)
        console_title_layout.setContentsMargins(5, 5, 5, 5)
        
        # 控制台标题
        console_title = QLabel("🖥️  Console")
        console_title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #4fc3f7;
            }
        """)
        console_title_layout.addWidget(console_title)
        
        # 添加弹簧，使按钮在右侧
        console_title_layout.addStretch()
        
        # === 新增：强制停止按钮 ===
        self.stop_button = QPushButton("⏹️")
        self.stop_button.setToolTip("强制停止运行")
        self.stop_button.setFixedSize(30, 30)
        self.stop_button.setEnabled(False)  # 默认禁用
        self.stop_button.clicked.connect(self.stop_running)
        console_title_layout.addWidget(self.stop_button)
        
        # 修复按钮
        self.fix_button = QPushButton("🔧")
        self.fix_button.setToolTip("修复错误")
        self.fix_button.setFixedSize(30, 30)
        self.fix_button.setEnabled(False)  # 默认禁用
        self.fix_button.clicked.connect(self.send_fix_request)
        console_title_layout.addWidget(self.fix_button)
        
        console_layout.addWidget(console_title_bar)
        
        # 控制台内容
        self.console_panel = QTextBrowser()
        self.console_panel.setReadOnly(True)
        self.console_panel.setFont(QFont("Consolas", 10))
        console_layout.addWidget(self.console_panel)
        
        v_splitter.addWidget(console_widget)
        
        # 3. 彗星面板 (右上)
        comet_widget = QWidget()
        comet_layout = QVBoxLayout(comet_widget)
        
        # 彗星面板标题栏（水平布局，包含标题和复选框）
        comet_title_bar = QWidget()
        comet_title_layout = QHBoxLayout(comet_title_bar)
        comet_title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 彗星面板标题
        comet_title = QLabel("☄️  Comet")
        comet_title_layout.addWidget(comet_title)
        
        # 添加弹簧，使复选框靠右
        comet_title_layout.addStretch()
        
        # === 新增：创建"附当前代码"复选框 ===
        self.attach_code_checkbox = QCheckBox("附当前代码")
        self.attach_code_checkbox.setChecked(False)  # 默认不选中
        self.attach_code_checkbox.setToolTip("勾选后，将把当前编辑器的全部代码随请求发送给AI")
        comet_title_layout.addWidget(self.attach_code_checkbox)
        
        comet_layout.addWidget(comet_title_bar)
        
        # AI回复显示区域
        self.comet_response = QTextEdit()
        self.comet_response.setReadOnly(True)
        self.comet_response.setFont(QFont("Consolas", 10))
        comet_layout.addWidget(self.comet_response, 3)
        
        # 输入区域
        input_layout = QHBoxLayout()
        
        self.comet_input = QLineEdit()
        self.comet_input.setPlaceholderText("输入您的要求...")
        self.comet_input.returnPressed.connect(self.send_to_comet)
        
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.send_to_comet)
        
        self.adopt_button = QPushButton("采用")
        self.adopt_button.clicked.connect(self.adopt_code)
        self.adopt_button.setEnabled(False)
        
        input_layout.addWidget(self.comet_input, 4)
        input_layout.addWidget(self.send_button, 1)
        input_layout.addWidget(self.adopt_button, 1)
        
        comet_layout.addLayout(input_layout)
        
        v_splitter.addWidget(comet_widget)
        v_splitter.addWidget(console_widget)
        
        h_splitter.addWidget(v_splitter)
        
        # 设置分割器初始比例
        h_splitter.setSizes([700, 500])
        v_splitter.setSizes([300, 200])
        
        main_layout.addWidget(h_splitter)
        
        # 最后应用主题，确保所有组件都已创建
        self.apply_full_theme()
    
    def create_shared_actions(self):
        """创建所有共享的Action，避免快捷键冲突"""
        # 文件菜单相关的共享action
        self.new_action = QAction("新建", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_file)
        
        self.open_action = QAction("打开", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_file)
        
        self.save_action = QAction("保存", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_code)
        
        self.save_as_action = QAction("另存为", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_as_file)
        
        self.exit_action = QAction("退出", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)
        
        # 编辑菜单相关的共享action
        self.undo_action = QAction("撤销", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.editor_panel.undo)
        
        self.redo_action = QAction("重做", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.editor_panel.redo)
        
        self.comment_action = QAction("注释/取消注释", self)
        self.comment_action.setShortcut("Ctrl+/")
        self.comment_action.triggered.connect(self.toggle_comment)
        
        self.duplicate_action = QAction("复制行", self)
        self.duplicate_action.setShortcut("Ctrl+D")
        self.duplicate_action.triggered.connect(self.duplicate_line)
        
        # 运行相关的共享action
        self.run_action = QAction("运行代码", self)
        self.run_action.setShortcut("Ctrl+Return")
        self.run_action.triggered.connect(self.run_code)
        
        # 主题相关的共享action - 去掉选项框
        self.dark_theme_action = QAction("深色主题", self)
        self.dark_theme_action.triggered.connect(lambda: self.switch_to_dark_theme())
        
        self.light_theme_action = QAction("浅色主题", self)
        self.light_theme_action.triggered.connect(lambda: self.switch_to_light_theme())
        
        # 设置相关的共享action
        self.set_api_key_action = QAction("设置API密钥", self)
        self.set_api_key_action.triggered.connect(self.set_api_key)
        
        # 帮助相关的共享action
        self.about_action = QAction("关于PyComet", self)
        self.about_action.triggered.connect(self.show_about)
        
        self.help_action = QAction("使用帮助", self)
        self.help_action.triggered.connect(self.show_help)
    
    def apply_console_theme(self):
        """应用控制台主题"""
        if self.current_theme == "dark":
            self.console_panel.setStyleSheet("""
                QTextEdit {
                    background-color: #0c0c0c;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                }
            """)
        else:
            self.console_panel.setStyleSheet("""
                QTextEdit {
                    background-color: #f5f5f5;
                    color: #333333;
                    border: 1px solid #cccccc;
                }
            """)
    
    def apply_console_title_theme(self):
        """应用控制台标题主题"""
        # 查找标题标签
        console_title = None
        for child in self.findChildren(QLabel):
            if child.text() == "🖥️  Console":
                console_title = child
                break
        
        if console_title:
            if self.current_theme == "dark":
                console_title.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #4fc3f7;
                    }
                """)
            else:
                console_title.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #1565C0;
                    }
                """)
    
    def apply_fix_button_theme(self):
        """应用修复按钮主题"""
        if self.current_theme == "dark":
            self.fix_button.setStyleSheet("""
                QPushButton {
                    background-color: #1b5e20;
                    color: white;
                    border: 1px solid #2e7d32;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:enabled {
                    background-color: #2e7d32;
                }
                QPushButton:disabled {
                    background-color: #424242;
                    color: #757575;
                    border: 1px solid #424242;
                }
            """)
        else:
            self.fix_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:enabled {
                    background-color: #45a049;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #9e9e9e;
                    border: 1px solid #bdbdbd;
                }
            """)
    
    def apply_stop_button_theme(self):
        """应用停止按钮主题"""
        if self.current_theme == "dark":
            self.stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #c62828;
                    color: white;
                    border: 1px solid #d32f2f;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:enabled {
                    background-color: #d32f2f;
                }
                QPushButton:disabled {
                    background-color: #424242;
                    color: #757575;
                    border: 1px solid #424242;
                }
            """)
        else:
            self.stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: 1px solid #e53935;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover:enabled {
                    background-color: #e53935;
                }
                QPushButton:disabled {
                    background-color: #e0e0e0;
                    color: #9e9e9e;
                    border: 1px solid #bdbdbd;
                }
            """)
    
    def apply_comet_response_theme(self):
        """应用彗星响应区域主题"""
        if self.current_theme == "dark":
            self.comet_response.setStyleSheet("""
                QTextEdit {
                    background-color: #252526;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    min-height: 200px;
                }
            """)
        else:
            self.comet_response.setStyleSheet("""
                QTextEdit {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    min-height: 200px;
                }
            """)
    
    def apply_comet_input_theme(self):
        """应用彗星输入框主题"""
        if self.current_theme == "dark":
            self.comet_input.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #3c3c3c;
                    background-color: #252526;
                    color: #d4d4d4;
                }
            """)
        else:
            self.comet_input.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    border: 1px solid #cccccc;
                    background-color: #ffffff;
                    color: #333333;
                }
            """)
    
    def apply_send_button_theme(self):
        """应用发送按钮主题"""
        if self.current_theme == "dark":
            self.send_button.setStyleSheet("""
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
        else:
            self.send_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
    
    def apply_adopt_button_theme(self):
        """应用采用按钮主题"""
        if self.current_theme == "dark":
            self.adopt_button.setStyleSheet("""
                QPushButton {
                    background-color: #1b5e20;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2e7d32;
                }
            """)
        else:
            self.adopt_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    padding: 8px 16px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
    
    def apply_window_theme(self):
        """应用窗口主题"""
        if self.current_theme == "dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(30, 30, 30))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(30, 30, 30))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(0, 122, 204))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(palette)
        else:
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.black)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Highlight, QColor(33, 150, 243))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            self.setPalette(palette)
    
    def apply_full_theme(self):
        """应用完整主题"""
        # 应用窗口主题
        self.apply_window_theme()
        
        # 应用编辑器主题
        if self.current_theme == "dark":
            self.editor_panel.apply_dark_theme()
            self.editor_panel.line_number_area.is_dark_theme = True
        else:
            self.editor_panel.apply_light_theme()
            self.editor_panel.line_number_area.is_dark_theme = False
        
        # 应用彗星面板标题
        comet_title = self.findChild(QLabel)
        if comet_title and comet_title.text() == "☄️  Comet":
            if self.current_theme == "dark":
                comet_title.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #4fc3f7;
                        padding: 5px;
                        border-bottom: 1px solid #3c3c3c;
                    }
                """)
            else:
                comet_title.setStyleSheet("""
                    QLabel {
                        font-size: 14px;
                        font-weight: bold;
                        color: #1565C0;
                        padding: 5px;
                        border-bottom: 1px solid #cccccc;
                    }
                """)
        
        # 应用控制台标题主题
        self.apply_console_title_theme()
        
        # 应用其他部件主题
        self.apply_console_theme()
        self.apply_fix_button_theme()
        self.apply_stop_button_theme()  # 新增
        self.apply_comet_response_theme()
        self.apply_comet_input_theme()
        self.apply_send_button_theme()
        self.apply_adopt_button_theme()
        
        # 重绘行号区域
        self.editor_panel.line_number_area.update()
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单 - 使用共享的action
        file_menu = menubar.addMenu("文件")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        
        # 编辑菜单 - 使用共享的action
        edit_menu = menubar.addMenu("编辑")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.comment_action)
        edit_menu.addAction(self.duplicate_action)
        
        # 运行菜单 - 使用共享的action
        run_menu = menubar.addMenu("运行")
        run_menu.addAction(self.run_action)
        
        # 主题菜单 - 使用共享的action
        theme_menu = menubar.addMenu("主题")
        theme_menu.addAction(self.dark_theme_action)
        theme_menu.addAction(self.light_theme_action)
        
        # 设置菜单 - 使用共享的action
        settings_menu = menubar.addMenu("设置")
        settings_menu.addAction(self.set_api_key_action)
        
        # 帮助菜单 - 使用共享的action
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction(self.about_action)
        help_menu.addAction(self.help_action)
    
    def switch_to_dark_theme(self):
        """切换到深色主题"""
        if self.current_theme != "dark":
            self.current_theme = "dark"
            self.apply_full_theme()
    
    def switch_to_light_theme(self):
        """切换到浅色主题"""
        if self.current_theme != "light":
            self.current_theme = "light"
            self.apply_full_theme()
    
    def init_shortcuts(self):
        """初始化快捷键 - 现在不需要了，因为所有快捷键都在共享action中设置了"""
        pass
    
    def init_auto_save(self):
        """初始化自动保存"""
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(30000)  # 30秒
        
    def autosave(self):
        """自动保存当前内容"""
        try:
            content = self.editor_panel.toPlainText()
            with open(".comet_ide_autosave.py", "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.console_update_signal.emit(f"自动保存失败: {e}", "normal")
    
    def load_autosave(self):
        """加载自动保存的文件"""
        try:
            if os.path.exists(".comet_ide_autosave.py"):
                with open(".comet_ide_autosave.py", "r", encoding="utf-8") as f:
                    content = f.read()
                    self.editor_panel.setPlainText(content)
        except Exception as e:
            self.console_update_signal.emit(f"加载自动保存文件失败: {e}", "normal")
    
    def decode_output(self, data):
        """解码子进程输出，处理可能的编码问题"""
        if data is None:
            return ""
        
        # 尝试不同的编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue
        
        # 如果所有编码都失败，尝试用replace错误处理
        try:
            return data.decode('utf-8', errors='replace')
        except (UnicodeDecodeError, AttributeError):
            return str(data)
    
    def run_code(self):
        """运行代码"""
        code = self.editor_panel.toPlainText()
        
        if not code.strip():
            self.console_update_signal.emit("没有代码可执行", "normal")
            return
        
        # 清空控制台
        self.console_panel.clear()
        # 禁用修复按钮
        self.fix_button.setEnabled(False)
        self.has_error = False
        
        # 执行时间使用纯文本
        self.console_update_signal.emit(f"执行时间: {datetime.now().strftime('%H:%M:%S')}", "normal")
        
        # 保存当前代码用于可能的修复
        self.current_running_code = code
        
        # 启用停止按钮
        self.stop_button.setEnabled(True)
        self.is_running = True
        
        # === 检测是否需要交互式输入 ===
        if "input(" in code:
            # 如果检测到 input 调用，则通过自动保存的文件进行交互式执行
            self.execute_with_input(code)
        else:
            # 原有逻辑：在新线程中执行非交互式代码
            self.execute_non_interactive(code)
    
    def execute_with_input(self, code):
        """执行需要用户交互输入的代码 - 简化为直接在cmd/终端中运行"""
        try:
            # 1. 将代码保存到自动保存文件
            temp_file_path = ".comet_ide_autosave.py"
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 2. 在控制台提示用户
            self.console_update_signal.emit(
                "检测到交互式代码。正在启动终端窗口执行此文件，请在新窗口中查看输出和进行输入...",
                "normal"
            )
            
            # 3. 在新终端窗口中执行文件
            try:
                if platform.system() == "Windows":
                    # Windows: 在新cmd窗口中执行
                    cmd_command = f'start cmd.exe /k "python {temp_file_path} && echo. && echo 程序执行完毕。"'
                    subprocess.Popen(cmd_command, shell=True)
                elif platform.system() == "Darwin":
                    # macOS: 在Terminal中执行
                    cmd_command = f'osascript -e \'tell app "Terminal" to do script "cd \\"{os.getcwd()}\\" && python3 {temp_file_path} && echo \\"程序执行完毕，按任意键关闭窗口...\\" && read"\''
                    subprocess.Popen(cmd_command, shell=True)
                else:
                    # Linux: 在终端中执行
                    cmd_command = f'gnome-terminal -- bash -c "python3 {temp_file_path}; echo \\"程序执行完毕，按任意键关闭窗口...\\"; read"'
                    subprocess.Popen(cmd_command, shell=True)
                
                self.console_update_signal.emit("已在终端窗口中启动程序执行", "normal")
                
            except Exception as e:
                self.console_update_signal.emit(f"启动终端执行失败: {e}", "failure")
                self.console_update_signal.emit(f"请手动在终端中执行: python {temp_file_path}", "normal")
            
            # 4. 立即禁用停止按钮，因为程序在外部终端运行，无法控制
            self.is_running = False
            self.stop_button.setEnabled(False)
            
        except Exception as e:
            # 捕获文件保存等初始化阶段的异常
            self.console_update_signal.emit(f"处理交互式代码失败: {e}", "failure")
            self.has_error = True
            QMetaObject.invokeMethod(self.fix_button, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
    
    def execute_non_interactive(self, code):
        """执行非交互式代码"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        
        # 在新线程中执行代码
        def execute():
            try:
                # 使用subprocess.Popen而不是run，以便能够停止进程
                self.non_interactive_process = subprocess.Popen(
                    [sys.executable, temp_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # 实时读取输出
                stdout_lines = []
                stderr_lines = []
                
                def read_stdout():
                    for line in self.non_interactive_process.stdout:
                        if line:
                            stdout_lines.append(line)
                            self.console_update_signal.emit(line.rstrip(), "normal")
                
                def read_stderr():
                    for line in self.non_interactive_process.stderr:
                        if line:
                            stderr_lines.append(line)
                            self.console_update_signal.emit(line.rstrip(), "failure")
                            self.has_error = True
                
                # 创建线程读取输出
                stdout_thread = threading.Thread(target=read_stdout)
                stderr_thread = threading.Thread(target=read_stderr)
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # 等待进程结束
                self.non_interactive_process.wait()
                
                # 等待输出线程结束
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                returncode = self.non_interactive_process.returncode
                
                if returncode == 0:
                    self.console_update_signal.emit("执行完成", "success")
                else:
                    self.console_update_signal.emit(f"执行失败，返回码: {returncode}", "failure")
                    self.has_error = True
                
                # 如果有错误，启用修复按钮
                if self.has_error:
                    QMetaObject.invokeMethod(self.fix_button, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
                
            except Exception as e:
                self.console_update_signal.emit(f"执行错误: {e}", "failure")
                self.has_error = True
                QMetaObject.invokeMethod(self.fix_button, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
            finally:
                # 发送进程完成信号
                self.process_finished_signal.emit()
                
                try:
                    os.unlink(temp_file)
                except:
                    pass
        
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
    
    def stop_running(self):
        """强制停止正在运行的程序"""
        if not self.is_running:
            return
        
        self.console_update_signal.emit("正在停止程序...", "normal")
        
        # 停止交互式进程
        if self.input_process and self.input_process.poll() is None:
            try:
                self.input_process.terminate()
                time.sleep(0.5)
                if self.input_process.poll() is None:
                    self.input_process.kill()
                # 修改：不显示错误信息，改为普通提示
                self.console_update_signal.emit("程序已强制停止", "normal")
            except:
                self.console_update_signal.emit("停止程序时发生异常", "normal")
        
        # 停止非交互式进程
        if self.non_interactive_process and self.non_interactive_process.poll() is None:
            try:
                self.non_interactive_process.terminate()
                time.sleep(0.5)
                if self.non_interactive_process.poll() is None:
                    self.non_interactive_process.kill()
                # 修改：不显示错误信息，改为普通提示
                self.console_update_signal.emit("程序已强制停止", "normal")
            except:
                self.console_update_signal.emit("停止程序时发生异常", "normal")
        
        # 更新状态
        self.is_running = False
        self.stop_button.setEnabled(False)
        
        # === 关键修改：注释掉以下两行，防止强制停止被误判为程序错误 ===
        # self.has_error = True
        # QMetaObject.invokeMethod(self.fix_button, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
    
    def on_process_finished(self):
        """进程完成后的处理"""
        self.is_running = False
        self.stop_button.setEnabled(False)
    
    def update_console(self, text, color_type="normal"):
        """更新控制台显示（线程安全）"""
        # 严格区分信息类型
        if color_type == "success":
            # 成功信息：使用带颜色的HTML
            self.console_panel.append(f'<font color="#4CAF50"><b>{text}</b></font>')
        elif color_type == "failure":
            # 错误信息：使用带颜色的HTML
            self.console_panel.append(f'<font color="#2196F3">{text}</font>')
        else:
            # 普通文本：完全使用纯文本
            self.console_panel.append(text)
        
        # 滚动到底部
        self.console_panel.verticalScrollBar().setValue(
            self.console_panel.verticalScrollBar().maximum()
        )
    
    def send_fix_request(self):
        """发送错误修复请求到AI助手"""
        if not hasattr(self, 'current_running_code') or not self.current_running_code.strip():
            QMessageBox.warning(self, "无代码", "没有可修复的代码")
            return
        
        # 检查API密钥
        if not self.api_key:
            QMessageBox.warning(self, "无API密钥", "请先在菜单栏的'设置'中设置API密钥")
            return
        
        # 获取控制台中的错误信息
        console_content = self.console_panel.toPlainText()
        error_lines = []
        for line in console_content.split('\n'):
            if "执行失败" in line or "执行错误" in line or "执行超时" in line or "Traceback" in line or "Error" in line.lower() or "Exception" in line:
                error_lines.append(line)
        
        error_info = '\n'.join(error_lines[-10:])  # 取最后10行错误信息
        
        # 禁用发送按钮，显示状态
        self.send_button.setEnabled(False)
        self.send_button.setText("修复中...")
        self.comet_response.setText("Comet正在分析错误并修复...")
        self.adopt_button.setEnabled(False)
        
        # 标记这是修复模式
        self.is_fix_mode = True
        
        # 构建修复提示词
        prompt = f"""请修复以下Python代码中的错误：

原始代码：
{self.current_running_code}

错误信息：
{error_info}

请遵循以下规则：
1. 原有无错误的代码保持不变，仅修改有错误的地方
2. 有错误的代码应保持最小改动与极简风格，且完整可执行
3. 在关键修复处添加注释说明
4. 仅提供代码与注释，不需要多余的文字说明"""
        
        # API配置
        API_KEY = self.api_key
        URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        
        # 准备请求数据
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        data = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        
        # 在新线程中发送请求
        def make_request():
            try:
                response = requests.post(URL, headers=headers, json=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    # 发送信号更新UI
                    self.comet_response_signal.emit(ai_response)
                else:
                    error_msg = f"API请求失败: {response.status_code}\n{response.text}"
                    self.comet_error_signal.emit(error_msg)
                    
            except Exception as e:
                error_msg = f"请求错误: {str(e)}"
                self.comet_error_signal.emit(error_msg)
            
            # 请求完成，启用发送按钮
            self.request_finished_signal.emit()
        
        thread = threading.Thread(target=make_request)
        thread.daemon = True
        thread.start()
    
    def send_to_comet(self):
        """发送请求到AI助手"""
        user_input = self.comet_input.text().strip()
        if not user_input:
            QMessageBox.warning(self, "输入为空", "请输入您的要求")
            return
        
        # 检查API密钥
        if not self.api_key:
            QMessageBox.warning(self, "无API密钥", "请先在菜单栏的'设置'中设置API密钥")
            return
        
        # 禁用发送按钮，显示状态
        self.send_button.setEnabled(False)
        self.send_button.setText("思考中...")
        self.comet_response.setText("Comet正在思考...")
        self.adopt_button.setEnabled(False)
        
        # 重置修复模式标志
        self.is_fix_mode = False
        
        # === 修改提示词构建逻辑，根据复选框状态决定是否附加当前代码 ===
        base_prompt = f"""请严格遵守以下规则：要求是{user_input}。请根据要求只输出极简风格的python代码，并搭配逐行注释。"""
        
        # 如果用户勾选了"附当前代码"，则将当前代码附加到提示中
        final_prompt = base_prompt
        if hasattr(self, 'attach_code_checkbox') and self.attach_code_checkbox.isChecked():
            current_code = self.editor_panel.toPlainText()
            if current_code.strip():  # 如果当前有代码
                final_prompt = f"""{base_prompt}

当前编辑器中的代码如下，可供参考：

{current_code}

"""

# API配置
        API_KEY = self.api_key
        URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        
        # 准备请求数据
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        data = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "user", "content": final_prompt}  # 使用最终提示词
            ],
            "stream": False
        }
        
        # 在新线程中发送请求
        def make_request():
            try:
                response = requests.post(URL, headers=headers, json=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result["choices"][0]["message"]["content"]
                    # 发送信号更新UI
                    self.comet_response_signal.emit(ai_response)
                else:
                    error_msg = f"API请求失败: {response.status_code}\n{response.text}"
                    self.comet_error_signal.emit(error_msg)
                    
            except Exception as e:
                error_msg = f"请求错误: {str(e)}"
                self.comet_error_signal.emit(error_msg)
            
            # 请求完成，启用发送按钮
            self.request_finished_signal.emit()
        
        thread = threading.Thread(target=make_request)
        thread.daemon = True
        thread.start()
    
    def update_comet_response(self, response_text):
        """更新AI响应显示（线程安全）"""
        # 统一处理：去掉可能存在的首尾格式说明行
        lines = response_text.strip().split('\n')
        if len(lines) > 2:
            # 去掉第一行和最后一行
            cleaned_text = '\n'.join(lines[1:-1])
        else:
            cleaned_text = response_text

        self.comet_response.setText(cleaned_text)
        self.adopt_button.setEnabled(True)
    
    def update_comet_error(self, error_text):
        """更新AI错误显示（线程安全）"""
        self.comet_response.setText(error_text)
    
    def enable_send_button(self):
        """启用发送按钮（线程安全）"""
        self.send_button.setEnabled(True)
        self.send_button.setText("发送")
    
    def adopt_code(self):
        """采用AI生成的代码 - 修复模式支持撤销/重做"""
        ai_code = self.comet_response.toPlainText()
        if not ai_code.strip():
            QMessageBox.warning(self, "无内容", "没有可采用的代码")
            return
        
        # 检查是否是修复模式
        if hasattr(self, 'is_fix_mode') and self.is_fix_mode:
            # 修复模式：替换所有代码，但支持撤销/重做
            cursor = self.editor_panel.textCursor()
            
            # 开始一个编辑块，这样整个替换操作被视为一个撤销操作
            cursor.beginEditBlock()
            
            try:
                # 选中整个文档
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                
                # 插入修复后的代码（这会替换选中的整个文档）
                cursor.insertText(ai_code)
                
                # 在控制台中显示提示
                self.console_update_signal.emit("已用修复后的代码替换当前所有代码", "success")
            finally:
                # 结束编辑块
                cursor.endEditBlock()
            
            # 重置修复模式标志
            self.is_fix_mode = False
        else:
            # 普通模式：在光标处插入
            cursor = self.editor_panel.textCursor()
            
            # 检查光标是否在行首
            cursor_position = cursor.position()
            cursor.movePosition(QTextCursor.StartOfLine)
            line_start_position = cursor.position()
            cursor.setPosition(cursor_position)  # 恢复光标位置
            
            # 判断是否需要换行
            if cursor_position > line_start_position:
                # 不在行首，先换行
                cursor.insertText('\n' + ai_code)
            else:
                # 在行首，直接插入
                cursor.insertText(ai_code)
    
    def toggle_comment(self):
        """注释/取消注释当前行或选中行"""
        cursor = self.editor_panel.textCursor()
        
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # 获取选中的文本块
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.StartOfBlock)
            start_block = cursor.block().blockNumber()
            
            cursor.setPosition(end)
            cursor.movePosition(QTextCursor.StartOfBlock)
            end_block = cursor.block().blockNumber()
            
            # 获取所有行
            lines = self.editor_panel.toPlainText().split('\n')
            
            # 检查是否所有行都已注释
            all_commented = all(line.strip().startswith('#') for i, line in enumerate(lines) 
                              if start_block <= i <= end_block and line.strip())
            
            # 添加或移除注释
            for i in range(start_block, end_block + 1):
                if i < len(lines):
                    if all_commented:
                        # 移除注释
                        if lines[i].strip().startswith('#'):
                            # 找到第一个#的位置
                            for j, ch in enumerate(lines[i]):
                                if ch == '#':
                                    # 检查#后面是否有一个空格
                                    if j+1 < len(lines[i]) and lines[i][j+1] == ' ':
                                        # 去掉#和后面的一个空格
                                        lines[i] = lines[i][:j] + lines[i][j+2:]
                                    else:
                                        # 只去掉#
                                        lines[i] = lines[i][:j] + lines[i][j+1:]
                                    break
                    else:
                        # 添加注释
                        lines[i] = '# ' + lines[i] if lines[i].strip() else lines[i]
            
            # 更新文本
            cursor.select(QTextCursor.Document)
            cursor.insertText('\n'.join(lines))
            
            # 恢复选中状态
            cursor.setPosition(self.editor_panel.document().findBlockByNumber(start_block).position())
            for _ in range(end_block - start_block):
                cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            self.editor_panel.setTextCursor(cursor)
        else:
            # 没有选中文本，处理当前行
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            line = cursor.selectedText()
            
            if line.strip().startswith('#'):
                # 移除注释
                # 找到第一个#的位置
                for j, ch in enumerate(line):
                    if ch == '#':
                        # 检查#后面是否有一个空格
                        if j+1 < len(line) and line[j+1] == ' ':
                            # 去掉#和后面的一个空格
                            new_line = line[:j] + line[j+2:]
                        else:
                            # 只去掉#
                            new_line = line[:j] + line[j+1:]
                        cursor.insertText(new_line)
                        break
            else:
                # 添加注释
                cursor.insertText('# ' + line)
    
    def duplicate_line(self):
        """复制当前行到下一行"""
        cursor = self.editor_panel.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        
        cursor.movePosition(QTextCursor.EndOfLine)
        cursor.insertText('\n' + line_text)
        
        # 移动到新行开头
        cursor.movePosition(QTextCursor.Down)
        cursor.movePosition(QTextCursor.StartOfLine)
        self.editor_panel.setTextCursor(cursor)
    
    def save_code(self):
        """保存代码到自动保存文件"""
        try:
            # 保存到自动保存文件
            content = self.editor_panel.toPlainText()
            with open(".comet_ide_autosave.py", "w", encoding="utf-8") as f:
                f.write(content)
            
            self.console_update_signal.emit(f"代码已保存到自动保存文件: .comet_ide_autosave.py", "normal")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错: {e}")
    
    def save_as_file(self):
        """另存为文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "", "Python文件 (*.py);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.editor_panel.toPlainText())
                self.console_update_signal.emit(f"代码已保存到: {file_path}", "normal")
            except Exception as e:
                QMessageBox.critical(self, "保存失败", f"保存文件时出错: {e}")
    
    def open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "Python文件 (*.py);;所有文件 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.editor_panel.setPlainText(content)
                self.console_update_signal.emit(f"已打开文件: {file_path}", "normal")
            except Exception as e:
                QMessageBox.critical(self, "打开失败", f"打开文件时出错: {e}")
    
    def new_file(self):
        """新建文件"""
        self.editor_panel.clear()
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>PyComet</h2>
        <p>版本: 1.4.0</p>
        <p>一个轻量级的Python集成开发环境</p>
        <p>功能特点:</p>
        <ul>
            <li>轻量级Python代码编辑与运行</li>
            <li>AI代码助手(Comet)</li>
            <li>智能错误修复功能</li>
            <li>语法高亮和自动缩进</li>
            <li>自动保存功能</li>
            <li>支持交互式输入 - 通过外部终端</li>
            <li>强制停止运行功能</li>
            <li>常用编辑快捷键</li>
        </ul>
        <p>© 2026 PyComet</p>
        """
        
        QMessageBox.about(self, "关于PyComet", about_text)
    
    def show_help(self):
        """显示帮助对话框 - 改为可滚动定长宽"""
        help_text = """
        <h2>PyComet 使用帮助</h2>
        
        <h3>基本操作:</h3>
        <ul>
            <li><b>运行代码:</b> 点击菜单栏的运行->运行代码或按Ctrl+Enter</li>
            <li><b>打开文件:</b> 点击菜单栏的文件->打开或按Ctrl+O</li>
        </ul>
        
        <h3>编辑快捷键:</h3>
        <ul>
            <li><b>注释/取消注释:</b> Ctrl+/</li>
            <li><b>复制行:</b> Ctrl+D</li>
            <li><b>撤销:</b> Ctrl+Z</li>
            <li><b>重做:</b> Ctrl+Y 或 Ctrl+Shift+Z</li>
            <li><b>增加缩进:</b> Tab</li>
            <li><b>减少缩进:</b> Ctrl+Tab</li>
        </ul>
        
        <h3>AI助手(Comet):</h3>
        <ul>
            <li>在右侧Comet面板的输入框中描述您的需求</li>
            <li>点击"发送"按钮或按Enter键提交</li>
            <li>AI生成的代码会显示在响应区域</li>
            <li>点击"采用"按钮将代码插入到编辑器中</li>
        </ul>
        
        <h3>错误修复功能:</h3>
        <ul>
            <li>当代码运行出错时，控制台标题栏右侧会显示🔧修复按钮</li>
            <li>点击按钮，AI会分析错误并提供修复后的完整代码</li>
            <li>在修复模式下，点击"采用"按钮会替换所有代码</li>
        </ul>
        
        <h3>交互式输入支持:</h3>
        <ul>
            <li>当代码中包含input()函数时，会自动启用交互式执行模式</li>
            <li>系统会自动打开终端窗口执行此文件</li>
        </ul>
        
        <h3>强制停止功能:</h3>
        <ul>
            <li>当程序正在运行时，控制台标题栏右侧会显示⏹️停止按钮</li>
            <li>点击按钮可强制停止正在运行的程序</li>
            <li>适用于长时间运行或陷入死循环的程序</li>
        </ul>
        
        <h3>文件保存:</h3>
        <ul>
            <li><b>自动保存:</b> 每30秒自动保存到.comet_ide_autosave.py文件</li>
            <li><b>手动保存 (Ctrl+S):</b> 保存到.comet_ide_autosave.py文件</li>
            <li><b>另存为 (Ctrl+Shift+S):</b> 选择其他位置和文件名保存</li>
        </ul>
        
        <h3>主题切换:</h3>
        <ul>
            <li>在"主题"菜单中选择深色或浅色主题</li>
        </ul>
        
        <h3>API密钥设置:</h3>
        <ul>
            <li>首次运行或API密钥无效时，会弹出设置对话框</li>
            <li>您可以在"设置"菜单中随时更改API密钥</li>
            <li>密钥保存在comet_config.json配置文件中</li>
        </ul>
        
        <h3>自动恢复:</h3>
        <p>程序启动时会自动加载.comet_ide_autosave.py文件中的内容，以便恢复上次的编辑</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("使用帮助")
        dialog.setFixedSize(600, 500)  # 定长宽
        
        # 创建布局
        layout = QVBoxLayout(dialog)
        
        # 创建可滚动的文本区域
        text_browser = QTextBrowser()
        text_browser.setHtml(help_text)
        text_browser.setOpenExternalLinks(True)
        
        # 添加到布局
        layout.addWidget(text_browser)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        # 显示对话框
        dialog.exec_()
    
    def closeEvent(self, event):
        """关闭事件，不清理自动保存文件，以便恢复"""
        # 如果交互式进程仍在运行，则终止它
        if self.input_process and self.input_process.poll() is None:
            self.input_process.terminate()
            try:
                self.input_process.wait(timeout=2)
            except:
                self.input_process.kill()
        
        # 如果非交互式进程仍在运行，则终止它
        if self.non_interactive_process and self.non_interactive_process.poll() is None:
            self.non_interactive_process.terminate()
            try:
                self.non_interactive_process.wait(timeout=2)
            except:
                self.non_interactive_process.kill()
        
        # 不再删除自动保存文件，以便在意外断电等情况下恢复代码
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # 设置应用图标
    if os.path.exists("icon.ico"):
        app.setWindowIcon(QIcon("icon.ico"))
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    ide = CometIDE()
    ide.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()