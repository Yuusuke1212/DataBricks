"""
JRA-Data Collector カラーシステムとテーマ管理

レポート「セクション5: データ集約型アプリケーションのための戦略的カラーシステム」
Table 2に基づく統一カラーシステムの実装
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal
from qfluentwidgets import Theme, setTheme, qconfig, ConfigItem, BoolValidator


class AppTheme(Enum):
    """アプリケーションテーマ"""
    LIGHT = "Light"
    DARK = "Dark"
    AUTO = "Auto"


@dataclass
class ColorPalette:
    """カラーパレット定義"""
    # Base Colors
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    border: str
    
    # Accent Colors  
    primary: str
    primary_variant: str
    
    # Semantic Colors
    success: str
    warning: str
    error: str
    
    # Data Visualization Colors
    data_blue: str
    data_teal: str
    data_purple: str


class JRADataCollectorColors:
    """レポート Table 2: JRA-Data Collector アプリケーションカラーシステム"""
    
    LIGHT = ColorPalette(
        # Base
        background="#F3F3F3",
        surface="#FFFFFF", 
        text_primary="#000000",
        text_secondary="#616161",
        border="#E0E0E0",
        
        # Accent
        primary="#0078D4",
        primary_variant="#106EBE",
        
        # Semantic
        success="#107C10",
        warning="#F1C41B", 
        error="#D32F2F",
        
        # Data (Categorical)
        data_blue="#1984C5",
        data_teal="#009688",
        data_purple="#673AB7"
    )
    
    DARK = ColorPalette(
        # Base
        background="#202020",
        surface="#2D2D2D",
        text_primary="#FFFFFF", 
        text_secondary="#BDBDBD",
        border="#424242",
        
        # Accent
        primary="#409CFE",
        primary_variant="#106EBE",
        
        # Semantic
        success="#39D85A",
        warning="#FFD700",
        error="#FF5252",
        
        # Data (Categorical)
        data_blue="#22A7F0",
        data_teal="#4DB6AC", 
        data_purple="#9575CD"
    )


class ThemeManager(QObject):
    """テーマ管理システム"""
    
    themeChanged = Signal(AppTheme)
    
    def __init__(self):
        super().__init__()
        self._current_theme = AppTheme.DARK
        self._current_palette = JRADataCollectorColors.DARK
        
    @property
    def current_theme(self) -> AppTheme:
        """現在のテーマを取得"""
        return self._current_theme
        
    @property
    def current_palette(self) -> ColorPalette:
        """現在のカラーパレットを取得"""
        return self._current_palette
        
    def set_theme(self, theme: AppTheme):
        """テーマを設定"""
        if theme == self._current_theme:
            return
            
        self._current_theme = theme
        
        if theme == AppTheme.LIGHT:
            setTheme(Theme.LIGHT)
            self._current_palette = JRADataCollectorColors.LIGHT
        else:  # DARK or AUTO (現在はDARKとして扱う)
            setTheme(Theme.DARK)
            self._current_palette = JRADataCollectorColors.DARK
            
        self.themeChanged.emit(theme)
        
    def get_semantic_color(self, semantic_type: str) -> str:
        """セマンティックカラーを取得"""
        semantic_map = {
            'success': self._current_palette.success,
            'warning': self._current_palette.warning,
            'error': self._current_palette.error,
        }
        return semantic_map.get(semantic_type, self._current_palette.primary)
        
    def get_data_color(self, category: str) -> str:
        """データビジュアライゼーション用カラーを取得"""
        data_map = {
            'blue': self._current_palette.data_blue,
            'teal': self._current_palette.data_teal,
            'purple': self._current_palette.data_purple,
        }
        return data_map.get(category, self._current_palette.data_blue)
        
    def generate_stylesheet(self, widget_class: str = "") -> str:
        """現在のテーマに基づくスタイルシートを生成"""
        palette = self._current_palette
        
        return f"""
        /* JRA-Data Collector Custom Styling - {self._current_theme.value} Theme */
        
        QMainWindow {{
            background-color: {palette.background};
            color: {palette.text_primary};
        }}
        
        CardWidget {{
            background-color: {palette.surface};
            border: 1px solid {palette.border};
            border-radius: 8px;
        }}
        
        .primary-button {{
            background-color: {palette.primary};
            color: {palette.surface};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }}
        
        .primary-button:hover {{
            background-color: {palette.primary_variant};
        }}
        
        .success-indicator {{
            color: {palette.success};
        }}
        
        .warning-indicator {{
            color: {palette.warning};
        }}
        
        .error-indicator {{
            color: {palette.error};
        }}
        """


# グローバルテーママネージャーインスタンス
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """グローバルテーママネージャーを取得"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def initialize_theme_system(initial_theme: AppTheme = AppTheme.DARK) -> ThemeManager:
    """テーマシステムを初期化"""
    theme_manager = get_theme_manager()
    theme_manager.set_theme(initial_theme)
    return theme_manager 