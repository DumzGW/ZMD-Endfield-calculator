import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
from fractions import Fraction
from collections import defaultdict
from math import ceil
from scipy.optimize import linprog

import sys, os

def resource_path(relative_path):
    return os.path.join(BASE_DIR, relative_path)
def get_base_dir():
    # 打包后
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # 开发时
    return os.path.dirname(os.path.abspath(__file__))
BASE_DIR = get_base_dir()

# ===== 读取Excel =====
df = pd.read_excel(resource_path("factory_db.xlsx"), sheet_name="Recipes")
recipes = {}

def parse_inputs(s):
    d = {}
    if pd.isna(s): 
        return d
    for p in str(s).split(";"):
        if ":" not in p: 
            continue
        n, q = p.split(":", 1)
        d[n.strip()] = Fraction(q.strip())
    return d

for _, r in df.iterrows():
    out = r["output"]
    oq = Fraction(r["output_qty"])
    ins = parse_inputs(r["inputs"])
    tool = r["tool"]
    
    recipes[out] = {
        "inputs": {k: v / oq for k, v in ins.items()}, 
        "tool": tool,
        "output_qty": oq  
    }
products = list(recipes.keys())

# ===== 读取设备尺寸 =====
items_df = pd.read_excel(resource_path("factory_db.xlsx"), sheet_name="Items")
items_df = items_df.dropna(subset=["Select_tool", "size", "Nsize" , "ele"])
tool_size = {}
tool_nsize = {}
tool_ele={}

for _, r in items_df.iterrows():
    t = r["Select_tool"]
    tool_size[t] = Fraction(r["size"])
    tool_nsize[t] = Fraction(r["Nsize"])
    tool_ele[t] = Fraction(r["ele"])

# ===== 读取限制数据 =====
limit_df = pd.read_excel(resource_path("factory_db.xlsx"), sheet_name="Limit")
limit_items = {}
limit_areas = ["无限制"]  # 默认选项

# 获取地区列表（从B2开始）
if not limit_df.empty and len(limit_df.columns) > 1:
    # 跳过第一列，从第二列开始获取地区名
    for col in limit_df.columns[1:]:
        area = str(col).strip()
        if area and area != "nan" and area != "Unnamed: 0":
            limit_areas.append(area)

# 存储限制数据
limit_data = {}

# ===== GUI =====
root = tk.Tk()
root.geometry("1400x750")  # 增大窗口尺寸以适应新面板
root.title("产业链计算器")

# 全局变量，用于记录最后修改的行
last_modified_row = None

# ===== 创建主要框架 =====
# 使用PanedWindow创建可拖动的分隔线
main_pane = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5)
main_pane.pack(fill=tk.BOTH, expand=True)

# ===== 限制面板（最左侧） =====
limit_panel = tk.Frame(main_pane, width=250, bg="#e8f4f8")
main_pane.add(limit_panel, minsize=0, width=250)

# 限制面板标题
tk.Label(limit_panel, text="限制设置", font=("微软雅黑", 12, "bold"), bg="#e8f4f8").pack(pady=10)

# 地区选择下拉框
area_var = tk.StringVar()
area_var.set("无限制")  # 默认选择无限制

area_label = tk.Label(limit_panel, text="选择地区:", font=("微软雅黑", 10), bg="#e8f4f8")
area_label.pack(pady=(0, 5))

area_combo = ttk.Combobox(limit_panel, textvariable=area_var, 
                          values=limit_areas, font=("微软雅黑", 10), width=15)
area_combo.pack(pady=(0, 10))

# 限制项目框架（带滚动条）
limit_items_frame = tk.Frame(limit_panel, bg="#e8f4f8")
limit_items_frame.pack(fill=tk.BOTH, expand=True, padx=5)

# 创建Canvas和滚动条
limit_canvas = tk.Canvas(limit_items_frame, bg="#e8f4f8", highlightthickness=0)
limit_scrollbar = tk.Scrollbar(limit_items_frame, orient="vertical", 
                               command=limit_canvas.yview, width=15)  # 加粗滚动条
limit_scrollable_frame = tk.Frame(limit_canvas, bg="#e8f4f8")

# 配置滚动区域
def update_limit_canvas_region():
    limit_canvas.configure(scrollregion=limit_canvas.bbox("all"))
    
    # 检查是否需要滚动条
    frame_height = limit_scrollable_frame.winfo_reqheight()
    canvas_height = limit_items_frame.winfo_height()
    
    if frame_height <= canvas_height:
        # 内容太少，禁用滚动条
        limit_scrollbar.pack_forget()
    else:
        limit_scrollbar.pack(side="right", fill="y")

limit_scrollable_frame.bind("<Configure>", lambda e: root.after(10, update_limit_canvas_region))

limit_canvas.create_window((0, 0), window=limit_scrollable_frame, anchor="nw")
limit_canvas.configure(yscrollcommand=limit_scrollbar.set)

limit_canvas.pack(side="left", fill="both", expand=True)

# 只绑定到限制canvas的鼠标滚轮事件
def _on_limit_mousewheel(event):
    limit_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
limit_canvas.bind("<MouseWheel>", _on_limit_mousewheel)
limit_scrollable_frame.bind("<MouseWheel>", _on_limit_mousewheel)

# 存储限制输入框的引用和上一次的值
limit_entries = {}
last_limit_values = {}

def update_limit_display():
    """更新限制显示"""
    # 清空当前显示
    for widget in limit_scrollable_frame.winfo_children():
        widget.destroy()
    
    limit_entries.clear()
    last_limit_values.clear()
    
    selected_area = area_var.get()
    
    if selected_area == "无限制":
        # 显示提示信息
        tk.Label(limit_scrollable_frame, text="未选择地区\n无限制设置", 
                font=("微软雅黑", 10), bg="#e8f4f8", fg="gray", pady=20).pack()
        refresh()  # 更新计算结果
        return
    
    # 查找选中的地区列
    area_column = None
    for col in limit_df.columns:
        if str(col).strip() == selected_area:
            area_column = col
            break
    
    if area_column is None:
        tk.Label(limit_scrollable_frame, text="地区数据未找到", 
                font=("微软雅黑", 10), bg="#e8f4f8", fg="red").pack()
        refresh()  # 更新计算结果
        return
    
    # 获取限制项
    limit_count = 0
    
    for idx, row in limit_df.iterrows():
        item_name = str(row.iloc[0]).strip()  # 第一列为项目名称
        
        if pd.isna(item_name) or item_name == "nan":
            continue
            
        # 获取限制值
        limit_value = row[area_column]
        
        # 如果限制值为空，则不显示
        if pd.isna(limit_value):
            continue
        
        # 检查项目是材料还是设备
        item_type = "未知"
        
        # 检查是否是材料
        if 'materials' in items_df.columns:
            materials_series = items_df['materials'].astype(str)
            if item_name in materials_series.values:
                item_type = "材料"
        
        # 检查是否是设备
        if 'Select_tool' in items_df.columns:
            tool_series = items_df['Select_tool'].astype(str)
            if item_name in tool_series.values:
                item_type = "设备"
        
        # 创建限制项框架
        item_frame = tk.Frame(limit_scrollable_frame, bg="#e8f4f8", pady=3)
        item_frame.pack(fill=tk.X, padx=5)
        
        # 项目标签
        item_label = tk.Label(item_frame, text=f"{item_name} ({item_type})", 
                             font=("微软雅黑", 9), bg="#e8f4f8", width=20, anchor="w")
        item_label.pack(side=tk.LEFT)
        
        # 限制值输入框
        limit_var = tk.StringVar()
        try:
            limit_value_float = float(limit_value)
            limit_var.set(str(f"{limit_value_float:.2f}"))
        except:
            limit_var.set("0")
        
        limit_entry = tk.Entry(item_frame, textvariable=limit_var, 
                              font=("微软雅黑", 9), width=8, justify="right")
        limit_entry.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 存储上一次的值
        try:
            last_limit_values[item_name] = float(limit_value)
        except:
            last_limit_values[item_name] = 0
        
        # 绑定事件
        def on_limit_focus_in(event, item=item_name):
            # 记录当前值作为旧值
            if item in limit_entries:
                entry_widget = limit_entries[item]["entry"]
                try:
                    last_limit_values[item] = Fraction(entry_widget.get()) if entry_widget.get() else 0
                except:
                    last_limit_values[item] = 0
        
        def on_limit_focus_out(event, item=item_name):
    # 检查新的限制值是否会导致已有消耗超过限制
            if item in limit_entries:
                entry_widget = limit_entries[item]["entry"]
                try:
                    new_value = float(entry_widget.get()) if entry_widget.get() else 0
                    old_value = last_limit_values.get(item, 0)
                    
                    # 计算当前消耗
                    current_consumption = get_current_consumption(item)
                    
                    if new_value < current_consumption:
                        # 弹出警告并恢复原值
                        entry_widget.delete(0, tk.END)
                        entry_widget.insert(0, str(old_value))
                        tk.messagebox.showwarning(
                            "限制警告",
                            f"警告：当前{item}的消耗为{current_consumption:.2f}，大于您输入的限制值{new_value:.2f}。\n限制值已恢复为{old_value}。"
                        )
                    else:
                        # 更新上一次的值
                        last_limit_values[item] = new_value
                        # 重置调整状态
                        reset_adjustment_state()
                except ValueError:
                    # 如果输入的不是数字，恢复原值
                    entry_widget.delete(0, tk.END)
                    entry_widget.insert(0, str(last_limit_values.get(item, 0)))
        limit_entry.bind("<FocusIn>", on_limit_focus_in)
        limit_entry.bind("<FocusOut>", on_limit_focus_out)
        
        # 存储引用
        limit_entries[item_name] = {
            "entry": limit_entry,
            "var": limit_var,
            "type": item_type
        }
        
        limit_count += 1
    
    if limit_count == 0:
        tk.Label(limit_scrollable_frame, text="该地区无限制项目", 
                font=("微软雅黑", 10), bg="#e8f4f8", fg="gray", pady=20).pack()
    
    # 更新计算结果
    refresh()

# 绑定地区选择事件
area_combo.bind("<<ComboboxSelected>>", lambda e: update_limit_display())

# 初始化限制显示


# ===== 产品输入面板 =====
left_panel = tk.Frame(main_pane, width=300, bg="#f0f0f0")
main_pane.add(left_panel, minsize=0, width=300)

# 左侧面板标题
tk.Label(left_panel, text="产品选择", font=("微软雅黑", 12, "bold"), bg="#f0f0f0").pack(pady=10)

# 存储产品行和最后修改的行
rows = []

# ===== 添加产品的函数 =====
def add_row():
    r = len(rows)
    
    # 创建一行框架
    row_frame = tk.Frame(left_panel, bg="#f0f0f0")
    row_frame.pack(fill=tk.X, padx=10, pady=3)
    
    # 产品选择框
    p = ttk.Combobox(row_frame, values=products, width=18, font=("微软雅黑", 10))
    p.pack(side=tk.LEFT, padx=(0, 5))
    
    # 绑定产品选择事件
    def on_product_select(event):
        global last_modified_row
        last_modified_row = (p, q)
        refresh()
    
    p.bind("<<ComboboxSelected>>", on_product_select)
    
    # 数量输入框
    q = tk.Entry(row_frame, width=10, font=("微软雅黑", 10))
    q.pack(side=tk.LEFT, padx=(0, 5))
    
    # 绑定事件
    def on_quantity_key(event):
        global last_modified_row
        last_modified_row = (p, q)
        # 延迟一点执行，等待输入完成
        left_panel.after(100, refresh)
    
    def on_quantity_focus(event):
        global last_modified_row
        last_modified_row = (p, q)
    
    q.bind("<KeyRelease>", on_quantity_key)
    q.bind("<FocusIn>", on_quantity_focus)
    
    # 删除按钮 - 调整宽度
    def delete():
        global last_modified_row
        row_frame.destroy()
        if (p, q) == last_modified_row:
            last_modified_row = None
        rows.remove((p, q))
        refresh()
    
    b = tk.Button(row_frame, text="删除", command=delete, 
                  font=("微软雅黑", 10), width=8, bg="#FF6B6B", fg="white")
    b.pack(side=tk.LEFT)
    
    rows.append((p, q))
    refresh()

# 添加产品按钮 - 缩小尺寸
add_btn = tk.Button(left_panel, text="添加产品", command=add_row, 
                    font=("微软雅黑", 10), bg="#4CAF50", fg="white", 
                    padx=10, pady=5)
add_btn.pack(pady=10)

# ===== 中间信息面板 =====
mid_panel = tk.Frame(main_pane, width=350)
main_pane.add(mid_panel, minsize=0, width=350)

# 信息面板标题
tk.Label(mid_panel, text="计算结果", font=("微软雅黑", 12, "bold")).pack(pady=10)

# 信息面板框架
info_frame = tk.Frame(mid_panel)
info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

# 创建Text和滚动条
info_text = tk.Text(
    info_frame,
    font=("微软雅黑", 10),
    wrap=tk.WORD,
    padx=10,
    pady=10
)
info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scroll = tk.Scrollbar(info_frame, command=info_text.yview, width=15)  # 加粗滚动条
scroll.pack(side=tk.RIGHT, fill=tk.Y)
info_text.config(yscrollcommand=scroll.set)
# ===== 右侧画布面板 =====
right_panel = tk.Frame(main_pane)
main_pane.add(right_panel, minsize=500)

# 创建画布
canvas = tk.Canvas(right_panel, bg="white", relief=tk.SUNKEN, bd=2)
canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
# 拖动功能
def drag_start(e):
    canvas.scan_mark(e.x, e.y)
def drag_move(e):
    canvas.scan_dragto(e.x, e.y, gain=1)
canvas.bind("<ButtonPress-1>", drag_start)
canvas.bind("<B1-Motion>", drag_move)
# 缩放功能
scale = 1.0
def zoom(e):
    global scale
    factor = 1.1 if e.delta > 0 else 0.9
    scale *= factor
    canvas.scale("all", e.x, e.y, factor, factor)
canvas.bind("<MouseWheel>", zoom)


# ===== 在添加产品按钮下面添加最优化按钮 =====

# ===== 修改后的自动最优化计算函数 =====
def auto_optimize_calculation():
    """自动最优化计算，最大化总收入（修复 infeasible 问题）"""
    global rows
    
    selected_area = area_var.get()
    if selected_area == "无限制":
        tk.messagebox.showinfo("提示", "请先选择地区")
        return
    
    sheet_name = f"sell_{selected_area}"
    
    try:
        sell_df = pd.read_excel(resource_path("factory_db.xlsx"), sheet_name=sheet_name)
        
        if '商品名称' not in sell_df.columns or '价格' not in sell_df.columns:
            tk.messagebox.showerror("错误", f"销售表 {sheet_name} 格式错误")
            return
        
        # ===== 价格表 =====
        price_dict = {}
        for _, row in sell_df.iterrows():
            name = str(row['商品名称']).strip()
            try:
                price_dict[name] = float(row['价格'])
            except:
                pass
        
        if not price_dict:
            tk.messagebox.showerror("错误", "没有有效价格数据")
            return
        
        # ===== 用户需求 =====
        user_demand = {}
        for p, q in rows:
            try:
                prod = p.get()
                if prod and q.get():
                    qty = Fraction(q.get())
                    if qty > 0:
                        user_demand[prod] = qty
            except:
                pass
        
        # ===== 读取限制（关键修改点）=====
        current_limits = {}
        for item_name, entry_info in limit_entries.items():
            try:
                limit_value = Fraction(entry_info["var"].get())
                if limit_value > 0:
                    # ⭐ 直接使用总上限，不再减当前消耗
                    current_limits[item_name] = limit_value
            except:
                pass
        
        if not current_limits:
            tk.messagebox.showinfo("提示", "当前地区没有设置限制")
            return
        
        # ===== 可销售产品 =====
        sellable_products = [
            p for p in products if p in price_dict
        ]
        
        if not sellable_products:
            tk.messagebox.showinfo("提示", "没有可销售产品")
            return
        
        # ===== 最优化 =====
        optimized = optimize_production(
            sellable_products,
            price_dict,
            user_demand,
            current_limits,   # ⭐ 传总上限
            {}                # current_usage 不再需要
        )
        
        if optimized:
            show_optimization_result(
                optimized,
                price_dict,
                user_demand
            )
        else:
            tk.messagebox.showinfo("结果", "无法找到更优组合")
            
    except Exception as e:
        tk.messagebox.showerror("错误", str(e))

def calculate_current_usage(product_quantities):
    """计算给定产品数量的资源消耗（包括材料和设备）"""
    # 创建临时数据结构
    temp_base = defaultdict(Fraction)
    temp_machines = defaultdict(list)
    
    # 计算每个产品的消耗
    for product, qty in product_quantities.items():
        _calculate_consumption(product, qty, temp_base, temp_machines)
    
    # 合并结果 - 包括材料和设备
    usage = {}
    
    # 添加材料消耗
    for material, amount in temp_base.items():
        usage[material] = amount
    
    # 添加设备消耗（计算总使用量）
    for device, usage_list in temp_machines.items():
        total_usage = sum(usage_list)
        usage[device] = total_usage
    
    return usage

def optimize_production(sellable_products, price_dict, user_demand,
                        available_resources, current_usage):
    """
    线性规划最优化（稳定版）
    """
    
    if not sellable_products or not available_resources:
        return {p: user_demand.get(p, Fraction(0))
                for p in sellable_products}
    
    try:
        n_products = len(sellable_products)
        
        # ===== 目标函数 =====
        c = [-price_dict.get(p, 0) for p in sellable_products]
        
        all_resources = list(available_resources.keys())
        
        A_ub = []
        b_ub = []
        
        # ===== 资源约束 =====
        for resource in all_resources:
            row = []
            
            for product in sellable_products:
                temp_base = defaultdict(Fraction)
                temp_machines = defaultdict(list)
                
                _calculate_consumption(
                    product, Fraction(1),
                    temp_base, temp_machines
                )
                
                cons = Fraction(0)
                
                if resource in temp_base:
                    cons = temp_base[resource]
                elif resource in temp_machines:
                    cons = sum(temp_machines[resource])
                
                row.append(float(cons))
            
            A_ub.append(row)
            
            # ⭐ 加微小容差防止浮点误差 infeasible
            b_ub.append(float(available_resources[resource]) + 1e-9)
        
        # ===== 最小需求约束 =====
        for i, product in enumerate(sellable_products):
            md = user_demand.get(product, Fraction(0))
            if md > 0:
                row = [0]*n_products
                row[i] = -1
                A_ub.append(row)
                b_ub.append(-float(md))
        
        bounds = [(0, None)] * n_products
        
        result_linprog = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds,
            method='highs'
        )
        
        if not result_linprog.success:
            print("LP失败:", result_linprog.message)
            return {p: user_demand.get(p, Fraction(0))
                    for p in sellable_products}
        
        sol = result_linprog.x
        
        result = {}
        for i, p in enumerate(sellable_products):
            val = sol[i]
            frac = Fraction(int(val*36), 36)
            
            if frac > 0 or p in user_demand:
                result[p] = max(
                    frac,
                    user_demand.get(p, Fraction(0))
                )
        
        return result
        
    except Exception as e:
        print("LP异常:", e)
        return {p: user_demand.get(p, Fraction(0))
                for p in sellable_products}

def show_optimization_result(optimized_quantities, price_dict, user_demand):
    """显示最优化计算结果"""
    # 计算总收入
    total_income = 0
    optimization_added = {}  # 记录优化的增加部分
    for product, qty in optimized_quantities.items():
        price = price_dict.get(product, 0)
        user_qty = user_demand.get(product, Fraction(0))
        added_qty = qty - user_qty if qty > user_qty else Fraction(0)
        
        if added_qty > 0:
            optimization_added[product] = added_qty
        
        total_income += float(qty) * price
    
    # 计算用户原有收入
    original_income = 0
    for product, qty in user_demand.items():
        price = price_dict.get(product, 0)
        original_income += float(qty) * price
    
    # 转换为每小时收入
    total_income = total_income * 30 * 60  # 每2秒一次，一小时30*60次
    original_income = original_income * 30 * 60
    
    # 创建结果窗口
    result_window = tk.Toplevel(root)
    result_window.title("最优化计算结果")
    result_window.geometry("600x800")
    
    # 标题
    tk.Label(result_window, text="计算结果", 
             font=("微软雅黑", 14, "bold")).pack(pady=10)
    
    # 显示总收入和增长
    tk.Label(result_window, text=f"优化后收入: {total_income:.1f} / 小时", 
             font=("微软雅黑", 12), fg="green").pack()
    
    tk.Label(result_window, text=f"原有收入: {original_income:.1f} / 小时", 
             font=("微软雅黑", 12), fg="blue").pack()
    
    if original_income > 0:
        increase = total_income - original_income
        increase_percent = (increase / original_income) * 100 if original_income > 0 else 0
        tk.Label(result_window, text=f"收入增加: {increase:.1f} / 小时 ({increase_percent:.1f}%)", 
                 font=("微软雅黑", 12), fg="red").pack()
    
    # 创建滚动文本框显示详细结果
    frame = tk.Frame(result_window)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    scrollbar = tk.Scrollbar(frame, width=15)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    result_text = tk.Text(frame, font=("微软雅黑", 10), wrap=tk.WORD, 
                          yscrollcommand=scrollbar.set, height=20)
    result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=result_text.yview)
    
    # 添加结果内容
    result_text.insert(tk.END, "=== 优化结果详情 ===\n\n")
    
    # 显示所有产品
    for product, qty in sorted(optimized_quantities.items(), 
                               key=lambda x: price_dict.get(x[0], 0) * float(x[1]), 
                               reverse=True):
        price = price_dict.get(product, 0)
        user_qty = user_demand.get(product, Fraction(0))
        income = float(qty) * price * 30 * 60  # 每小时收入
        
        if product in optimization_added:
            result_text.insert(tk.END, 
                              f"📈 {product}:\n"
                              f"   原有产线: {str(user_qty)}\n"
                              f"   优化后产线: {str(qty)} (+{str(optimization_added[product])})\n"
                              f"   每2秒价格: {price:.2f}, 每小时收入: {income:.2f}\n\n")
        else:
            result_text.insert(tk.END, 
                              f"📊 {product}:\n"
                              f"   产线数量: {str(qty)} (无变化)\n"
                              f"   每2秒价格: {price:.2f}, 每小时收入: {income:.2f}\n\n")
    
    # 显示优化建议
    if optimization_added:
        result_text.insert(tk.END, "=== 优化建议 ===\n")
        for product, added_qty in optimization_added.items():
            result_text.insert(tk.END, f"• 增加 {product} 的产线: +{str(added_qty)}\n")
    else:
        result_text.insert(tk.END, "=== 优化建议 ===\n")
        result_text.insert(tk.END, "当前设置已经是最优的，无需调整。\n")
    
    # 禁用文本编辑
    result_text.config(state=tk.DISABLED)
    
    # 添加按钮
    button_frame = tk.Frame(result_window)
    button_frame.pack(pady=10)
    
    def apply_optimization():
        """应用优化结果到产品输入"""
        # 记录应用了哪些产品
        updated_products = []
        added_products = []
        
        # 首先，更新现有行中已有的产品
        for p, q in rows:
            try:
                product = p.get()
                if product in optimized_quantities:
                    # 获取优化后的数量
                    optimized_qty = optimized_quantities[product]
                    
                    # 获取当前数量（用户输入）
                    current_qty_str = q.get()
                    current_qty = Fraction(current_qty_str) if current_qty_str else Fraction(0)
                    
                    # 如果优化后的数量大于当前数量，则更新
                    if optimized_qty > current_qty:
                        q.delete(0, tk.END)
                        q.insert(0, str(optimized_qty))
                        updated_products.append(product)
                    
                    # 从字典中移除已处理的产品
                    del optimized_quantities[product]
            except:
                pass
        
        # 然后，添加优化结果中有但用户没有的产品
        for product, qty in optimized_quantities.items():
            if qty > 0:
                # 调用add_row函数添加新行
                add_row()  # 这会添加新的一行
                
                # 获取最后添加的行并设置产品名称和数量
                if rows:
                    last_p, last_q = rows[-1]
                    last_p.set(product)
                    last_q.delete(0, tk.END)
                    last_q.insert(0, str(qty))
                    added_products.append(product)
        
        # 刷新界面
        refresh()
        
        # 关闭结果窗口
        result_window.destroy()
        
        # 显示应用结果的详细信息
        message = "优化结果已应用！\n\n"
        if updated_products:
            message += f"更新了 {len(updated_products)} 个已有产品\n"
        if added_products:
            message += f"新增了 {len(added_products)} 个新产品\n"
        
        if not updated_products and not added_products:
            message += "没有需要更新的产品，您的输入已经是最优的！"
        
        tk.messagebox.showinfo("成功", message)
    
    apply_btn = tk.Button(button_frame, text="应用优化结果", 
                         command=apply_optimization,
                         font=("微软雅黑", 10), bg="#4CAF50", fg="white",
                         padx=15, pady=5)
    apply_btn.pack(side=tk.LEFT, padx=5)
    
    close_btn = tk.Button(button_frame, text="关闭", 
                         command=result_window.destroy,
                         font=("微软雅黑", 10), bg="#F44336", fg="white",
                         padx=15, pady=5)
    close_btn.pack(side=tk.LEFT, padx=5)


    
optimize_btn = tk.Button(left_panel, text="自动最优化计算", 
                        command=auto_optimize_calculation, 
                        font=("微软雅黑", 10), bg="#9C27B0", fg="white", 
                        padx=10, pady=5)
optimize_btn.pack(pady=5)





# ===== 添加"仅显示流程"功能 =====

# 创建变量跟踪"仅显示流程"状态
show_process_only_var = tk.BooleanVar(value=False)

# 存储原始窗口大小和位置
original_geometry = "1400x750"
original_panels_state = {}

# 在右上角添加"仅显示流程"勾选框
def create_show_process_checkbox():
    """在右上角创建仅显示流程勾选框"""
    # 创建一个框架来放置勾选框
    top_right_frame = tk.Frame(root)
    top_right_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    # 创建勾选框
    show_process_checkbox = tk.Checkbutton(
        top_right_frame,
        text="仅显示流程",
        variable=show_process_only_var,
        command=toggle_show_process_only,
        font=("微软雅黑", 9)
    )
    show_process_checkbox.pack()
    
    return top_right_frame, show_process_checkbox

# 创建切换函数
def toggle_show_process_only():
    """切换仅显示流程模式"""
    if show_process_only_var.get():
        # 进入仅显示流程模式
        root.overrideredirect(True)
        enter_process_only_mode()
    else:
        # 退出仅显示流程模式
        exit_process_only_mode()
        root.overrideredirect(False)

def enter_process_only_mode():
    """进入仅显示流程模式"""
    global original_geometry
    
    # 存储原始状态
    original_geometry = root.geometry()
    
    # 隐藏除了画布以外的所有面板
    limit_panel.pack_forget()
    left_panel.pack_forget()
    mid_panel.pack_forget()
    
    # 隐藏右上角的勾选框
    top_right_frame.place_forget()
    
    # 获取屏幕尺寸
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # 计算新窗口大小
    new_width = int(screen_width / 3.5)
    new_height = int(screen_height / 2)
    
    # 移动到屏幕右上角
    x_position = screen_width - new_width + 5  # 距离右边10像素
    y_position = -5  # 距离顶部
    
    # 设置窗口属性
    root.geometry(f"{new_width}x{new_height}+{x_position}+{y_position}")
    root.resizable(False, False)  # 禁止调整大小
    root.attributes('-topmost', True)  # 置顶
    
    # 调整画布面板大小
    right_panel.pack_propagate(False)
    right_panel.config(width=new_width, height=new_height)
    
    # 在画布下方添加取消勾选框
    cancel_frame = tk.Frame(right_panel, bg="white")
    cancel_frame.pack(side="top", fill="x", pady=0)
    
    cancel_checkbox = tk.Checkbutton(
        cancel_frame,
        text="取消仅显示流程",
        variable=show_process_only_var,
        command=toggle_show_process_only,
        font=("微软雅黑", 9),
        bg="white"
    )
    cancel_checkbox.pack()
    
    # 存储取消勾选框引用
    root.cancel_frame = cancel_frame
    
    # 刷新画布显示
    refresh()

def exit_process_only_mode():
    """退出仅显示流程模式"""
    # 恢复窗口属性
    root.geometry(original_geometry)
    root.resizable(True, True)  # 允许调整大小
    root.attributes('-topmost', False)  # 取消置顶
    
    # 显示所有面板
    main_pane.add(limit_panel, minsize=0, width=250)
    main_pane.add(left_panel, minsize=0, width=300)
    main_pane.add(mid_panel, minsize=0, width=350)
    
    # 移除取消勾选框
    if hasattr(root, 'cancel_frame'):
        root.cancel_frame.pack_forget()
    
    # 显示右上角的勾选框
    top_right_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    # 恢复画布面板大小
    right_panel.pack_propagate(True)
    
    # 刷新显示
    refresh()

# 创建右上角勾选框
top_right_frame, show_process_checkbox = create_show_process_checkbox()




# ===== 画节点 =====
def draw_node(x, y, text, typ):
    if typ == "material":
        r = 35
        canvas.create_oval(x-r, y-r, x+r, y+r, fill="#90CAF9")
    elif typ == "product":
        canvas.create_rectangle(x-45, y-30, x+45, y+30, fill="#FFCC80")
    else:
        canvas.create_polygon(x, y-35, x+45, y, x, y+35, x-45, y,
                              fill="#A5D6A7")
    canvas.create_text(x, y, text=text, font=("微软雅黑", 11, "bold"))

def get_width(prod):
    if prod not in recipes:
        return 1

    w = 0
    for mat, _ in recipes[prod]["inputs"].items():
        w += get_width(mat)

    return max(w, 1)

# ===== 递归绘图 =====
def draw_tree(prod, qty, x, y, base, machines, logistics):
    draw_node(x, y, f"{prod}\n{qty}x",
              "product" if prod in recipes else "material")

    if prod not in recipes:
        base[prod] += qty
        logistics["road_list"].append(qty)
        return

    tool = recipes[prod]["tool"]
    oq = recipes[prod]["output_qty"]
    machines[tool].append(qty / oq)
    logistics["road_list"].append(qty)
    
    ty = y + 120
    draw_node(x, ty, tool, "device")
    canvas.create_line(x, ty-35, x, y+35, arrow="last")

    inputs = list(recipes[prod]["inputs"].items())
    widths = [get_width(mat) for mat, _ in inputs]
    total_w = sum(widths)

    unit = 120   # 每个宽度单位对应像素
    left = x - total_w * unit / 2
    cur = left

    for (mat, need), w in zip(inputs, widths):
        cx = cur + w * unit / 2
        cy = y + 260
        total = need * qty
        canvas.create_line(cx, cy-35, x, ty+35, arrow="last")
        draw_tree(mat, total, cx, cy, base, machines, logistics)
        cur += w * unit

def calc_footprint(base, machines, logistics):
    # ===== 道路 =====
    road_cells = sum(ceil(x) for x in logistics["road_list"])

    # ===== 理论最低 =====
    min_cells = road_cells
    min_ele = 0
    for m, usage_list in machines.items():
        total_usage = sum(usage_list)
        machine_count = ceil(total_usage)
        if m in tool_size:
            min_cells += machine_count * tool_size[m]
            min_ele += machine_count * tool_ele[m]

    # ===== 真·不整合 =====
    non_integrated = road_cells

    for m, usage_list in machines.items():
        if m not in tool_size:
            continue

        size = tool_size[m]
        nsize = tool_nsize.get(m, 0)

        for u in usage_list:
            c = ceil(u)  # 每次独立取整
            non_integrated += c * (size + nsize)

    return min_cells, non_integrated, min_ele

# ===== 获取当前消耗 =====
def get_current_consumption(item_name):
    """获取指定项目的当前消耗"""
    # 计算当前消耗
    base = defaultdict(Fraction)
    machines = defaultdict(list) 
    logistics = {"road_list": []}
    valid = []
    
    for p, q in rows:
        try:
            prod = p.get()
            qty_str = q.get()
            if qty_str:
                qty = Fraction(qty_str)
            else:
                qty = Fraction(0)
            if prod and qty > 0:
                valid.append((prod, qty))
        except: 
            pass
    
    # 计算当前消耗
    for prod, qty in valid:
        _calculate_consumption(prod, qty, base, machines)
    
    # 检查是材料还是设备
    if item_name in base:
        return Fraction(base[item_name])
    elif item_name in machines:
        return Fraction(sum(machines[item_name]))
    
    return 0

def _calculate_consumption(prod, qty, base, machines):
    """递归计算消耗"""
    if prod not in recipes:
        base[prod] += qty
        return

    tool = recipes[prod]["tool"]
    oq = recipes[prod]["output_qty"]
    machines[tool].append(qty / oq)
    
    inputs = list(recipes[prod]["inputs"].items())
    for mat, need in inputs:
        total = need * qty
        _calculate_consumption(mat, total, base, machines)

# ===== 检查限制 =====
def check_limits(base, machines):
    """检查是否超出限制"""
    warnings = []
    
    selected_area = area_var.get()
    if selected_area == "无限制":
        return warnings
    
    # 检查材料限制
    for material, amount in base.items():
        if material in limit_entries:
            try:
                limit_value = Fraction(limit_entries[material]["var"].get())
                if Fraction(amount) > limit_value:
                    warnings.append(f"材料 {material} 超出限制: {Fraction(amount)} > {limit_value}")
            except (ValueError, KeyError):
                pass
    
    # 检查设备限制
    for device, usage_list in machines.items():
        if device in limit_entries:
            try:
                total_usage = sum(usage_list)
                limit_value = Fraction(limit_entries[device]["var"].get())
                if total_usage > limit_value:
                    warnings.append(f"设备 {device} 超出限制: {Fraction(total_usage)} > {limit_value}")
            except (ValueError, KeyError):
                pass
    
    return warnings

# ===== 自动调整函数 =====
def auto_adjust_quantity(base, machines, warnings):
    """自动调整产品数量直到不超出限制（只在超出限制时调整）"""
    global last_modified_row
    
    if area_var.get() == "无限制":
        return False  # 不需要调整
    
    # 如果没有最后修改的行，返回
    if not last_modified_row:
        return False
    
    product_combobox, quantity_entry = last_modified_row
    
    # 获取当前值
    try:
        current_qty = Fraction(quantity_entry.get()) if quantity_entry.get() else Fraction(0)
    except:
        return False  # 无效输入
    
    if current_qty <= 0:
        return False  # 数量为0或负数，不需要调整
    
    # 只有在有警告时才调整
    if not warnings:
        return False
    
    # 获取当前产品
    product = product_combobox.get()
    if not product:
        return False
    
    # 获取调整状态
    global adjustment_state
    if 'adjustment_state' not in globals():
        adjustment_state = {}
    
    # 初始化调整状态
    if product not in adjustment_state:
        adjustment_state[product] = {
            'original_qty': current_qty,  # 原始输入的数量
            'current_qty': current_qty,   # 当前调整到的数量
            'phase': 'decrease',          # 当前阶段：decrease(减少) / recover(恢复)
            'decrease_step': Fraction(1, 6),  # 减少步长
            'recover_step': Fraction(1, 180),  # 恢复步长（如果减少过多）
            'min_reached': False,         # 是否到达过最小值
            'min_qty': Fraction(0),       # 到达过的最小值
            'adjustment_count': 0,
            'max_adjustments': 50         # 最大调整次数
        }
    
    state = adjustment_state[product]
    
    # 检查调整次数
    if state['adjustment_count'] >= state['max_adjustments']:
        # 调整次数过多，停止调整
        del adjustment_state[product]
        return False
    
    # 检查当前是否还有警告
    current_warnings = check_limits_for_qty(product_combobox, state['current_qty'])
    has_current_warnings = len(current_warnings) > 0
    
    # 根据阶段和警告状态决定如何调整
    if state['phase'] == 'decrease':
        if has_current_warnings:
            # 还有警告，继续减少
            new_qty = state['current_qty'] - state['decrease_step']
            if new_qty < 0:
                new_qty = Fraction(0)
                state['min_reached'] = True
                state['min_qty'] = new_qty
            
            state['current_qty'] = new_qty
        else:
            # 没有警告了，记录最小值并进入恢复阶段
            state['min_reached'] = True
            state['min_qty'] = state['current_qty']
            state['phase'] = 'recover'
            # 稍微恢复一点（如果减少过多了）
            if state['current_qty'] < state['original_qty']:
                new_qty = state['current_qty'] + state['recover_step']
                # 确保恢复后不会超过原始数量
                if new_qty > state['original_qty']:
                    new_qty = state['original_qty']
                state['current_qty'] = new_qty
            else:
                # 已经调整完成
                del adjustment_state[product]
                return False
    
    elif state['phase'] == 'recover':
        # 恢复阶段：稍微增加一点，但确保不超过原始数量且不超限
        if state['current_qty'] < state['original_qty']:
            # 尝试增加一点
            test_qty = state['current_qty'] + state['recover_step']
            
            # 确保不超过原始数量
            if test_qty > state['original_qty']:
                test_qty = state['original_qty']
            
            # 检查增加后是否会超限
            if not will_exceed_limit_with_qty(product_combobox, test_qty):
                # 可以增加
                state['current_qty'] = test_qty
            else:
                # 增加后会超限，停止调整
                del adjustment_state[product]
                return False
        else:
            # 已经恢复到原始数量或更高，停止调整
            del adjustment_state[product]
            return False
    
    # 更新输入框
    quantity_entry.delete(0, tk.END)
    quantity_entry.insert(0, str(state['current_qty']))
    
    # 增加调整计数
    state['adjustment_count'] += 1
    
    return True
def check_limits_for_qty(product_combobox, test_qty):
    """检查给定的产品数量是否会导致超出限制"""
    # 创建一个临时的副本进行计算
    temp_base = defaultdict(Fraction)
    temp_machines = defaultdict(list)
    temp_logistics = {"road_list": []}
    
    # 只计算这一个产品的消耗
    product = product_combobox.get()
    if not product:
        return []
    
    # 递归计算消耗
    def _temp_calculate(prod, qty, base, machines):
        if prod not in recipes:
            base[prod] += qty
            return

        tool = recipes[prod]["tool"]
        oq = recipes[prod]["output_qty"]
        machines[tool].append(qty / oq)
        
        inputs = list(recipes[prod]["inputs"].items())
        for mat, need in inputs:
            total = need * qty
            _temp_calculate(mat, total, base, machines)
    
    # 计算测试数量的消耗
    _temp_calculate(product, test_qty, temp_base, temp_machines)
    
    # 检查是否超出限制
    selected_area = area_var.get()
    if selected_area == "无限制":
        return []
    
    warnings = []
    
    # 检查材料限制
    for material, amount in temp_base.items():
        if material in limit_entries:
            try:
                limit_value = Fraction(limit_entries[material]["var"].get())
                if Fraction(amount) > limit_value:
                    warnings.append(f"材料 {material} 超出限制")
            except (ValueError, KeyError):
                pass
    
    # 检查设备限制
    for device, usage_list in temp_machines.items():
        if device in limit_entries:
            try:
                total_usage = sum(usage_list)
                limit_value = Fraction(limit_entries[device]["var"].get())
                if total_usage > limit_value:
                    warnings.append(f"设备 {device} 超出限制")
            except (ValueError, KeyError):
                pass
    
    return warnings
def reset_adjustment_state():
    """重置所有调整状态"""
    global adjustment_state, last_modified_row
    adjustment_state = {}
    last_modified_row = None
    refresh()
def will_exceed_limit_with_qty(product_combobox, test_qty):
    """检查给定的产品数量是否会导致超出限制"""
    # 创建一个临时的副本进行计算
    temp_base = defaultdict(Fraction)
    temp_machines = defaultdict(list)
    temp_logistics = {"road_list": []}
    
    # 只计算这一个产品的消耗
    product = product_combobox.get()
    if not product:
        return False
    
    # 递归计算消耗
    def _temp_calculate(prod, qty, base, machines):
        if prod not in recipes:
            base[prod] += qty
            return

        tool = recipes[prod]["tool"]
        oq = recipes[prod]["output_qty"]
        machines[tool].append(qty / oq)
        
        inputs = list(recipes[prod]["inputs"].items())
        for mat, need in inputs:
            total = need * qty
            _temp_calculate(mat, total, base, machines)
    
    # 计算测试数量的消耗
    _temp_calculate(product, test_qty, temp_base, temp_machines)
    
    # 检查是否超出限制
    selected_area = area_var.get()
    if selected_area == "无限制":
        return False
    
    # 检查材料限制
    for material, amount in temp_base.items():
        if material in limit_entries:
            try:
                limit_value = Fraction(limit_entries[material]["var"].get())
                if Fraction(amount) > limit_value:
                    return True  # 会超限
            except (ValueError, KeyError):
                pass
    
    # 检查设备限制
    for device, usage_list in temp_machines.items():
        if device in limit_entries:
            try:
                total_usage = sum(usage_list)
                limit_value = Fraction(limit_entries[device]["var"].get())
                if total_usage > limit_value:
                    return True  # 会超限
            except (ValueError, KeyError):
                pass
    
    return False  # 不会超限
# ===== 刷新 =====
def refresh():
    canvas.delete("all")
    base = defaultdict(Fraction)
    machines = defaultdict(list) 
    logistics = {"road_list": []}
    valid = []
    
    for p, q in rows:
        try:
            prod = p.get()
            qty_str = q.get()
            if qty_str:
                qty = Fraction(qty_str)
            else:
                qty = Fraction(0)
            if prod and qty > 0:
                valid.append((prod, qty))
        except: 
            pass

    x = 200
    for prod, qty in valid:
        draw_tree(prod, qty, x, 80, base, machines, logistics)
        x += 600

    canvas.config(scrollregion=canvas.bbox("all"))

    # 更新信息面板
    txt = "=== 基础材料 ===\n"
    for k, v in base.items():
        txt += f"{k}: {float(v):.2f}\n"

    txt += "\n=== 设备需求 ===\n"
    for k, usage_list in machines.items():
        total = sum(usage_list)
        need = ceil(total)
        
        if total > 0:  # 只显示有需求的设备
            txt += (
                f"{k}:\n"
                f"  理论设备数 = {float(total):.2f}\n"
                f"  需求设备数 = {need}\n"
                f"  利用率 = {float(total/need*100):.1f}%\n"
            )
    
    # 计算占地面积
    if machines:
        min_cells, non_int, min_ele = calc_footprint(base, machines, logistics)
        txt += f"\n总电量需求： {float(min_ele):.2f}\n"
        txt += f"\n=== 占地面积 ===\n"
        txt += f"理论最低占地: {float(min_cells):.2f} 格\n"
        txt += f"不整合占地: {float(non_int):.2f} 格\n"
    
# 检查限制并显示警告
    warnings = check_limits(base, machines)
    if warnings:
        txt += f"\n=== 限制警告 ===\n"
        for warning in warnings:
            txt += f"⚠ {warning}\n"
        
        # 只在有警告时才自动调整
        if area_var.get() != "无限制" and last_modified_row:
            if auto_adjust_quantity(base, machines, warnings):
                txt += f"\n⚠ 正在调整产品数量以避免超出限制...\n"
                # 重新计算
                root.after(100, refresh)
    else:
        # 没有警告时，如果还有调整状态，清除它
        global adjustment_state
        if 'adjustment_state' in globals() and last_modified_row:
            product_combobox, _ = last_modified_row
            product = product_combobox.get()
            if product in adjustment_state:
                del adjustment_state[product]
    # 显示产品数量
    txt += f"\n=== 概览 ===\n"
    txt += f"当前产品数量: {len(valid)}\n"
    txt += f"总输入行数: {len(rows)}\n"
    txt += f"当前地区: {area_var.get()}\n"
    
    info_text.delete("1.0", "end")
    info_text.insert("end", txt)
update_limit_display()
root.mainloop()