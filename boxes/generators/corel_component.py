from pathlib import Path
import xml.etree.ElementTree as ET
from boxes import Boxes
from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.ops import unary_union
from shapely.affinity import translate, scale, rotate
import math

class CorelComponentGenerator(Boxes):
    """Generador que integra componentes SVG de CorelDRAW en diseños de Boxes.py.
    Permite combinar formas paramétricas con diseños personalizados importados."""
    
    ui_group = "Componentes Personalizados"

    def __init__(self):
        super().__init__()
        
        # Parámetros del componente
        self.argparser.add_argument(
            "--component_folder", type=str, default="trofeos",
            choices=["trofeos", "logos", "decoraciones"],
            help="Carpeta donde está el componente SVG (dentro de static/components/)"
        )
        self.argparser.add_argument(
            "--component_filename", type=str, default="f1_trophy.svg",
            help="Nombre del archivo SVG exportado desde CorelDRAW"
        )
        self.argparser.add_argument(
            "--component_scale", type=float, default=1.0,
            help="Escala del componente (1.0 = tamaño original del SVG)"
        )
        self.argparser.add_argument(
            "--component_rotation", type=float, default=0.0,
            help="Rotación del componente (grados)"
        )
        self.argparser.add_argument(
            "--component_x", type=float, default=0.0,
            help="Posición X del componente respecto al centro de la base (mm)"
        )
        self.argparser.add_argument(
            "--component_y", type=float, default=0.0,
            help="Posición Y del componente respecto al centro de la base (mm)"
        )
        
        # Parámetros de la base
        self.argparser.add_argument(
            "--base_shape", type=str, default="circle",
            choices=["circle", "rectangle", "none"],
            help="Forma base sobre la cual se coloca el componente"
        )
        self.argparser.add_argument(
            "--base_size", type=float, default=80.0,
            help="Diámetro (círculo) o lado (cuadrado) de la base (mm)"
        )
        self.argparser.add_argument(
            "--base_offset", type=float, default=5.0,
            help="Margen entre el componente y el borde de la base (mm)"
        )

    def load_svg_component(self, folder: str, filename: str, scale: float, rotation: float, x: float, y: float) -> Polygon | MultiPolygon | None:
        """Carga un SVG y lo convierte a polígonos de Shapely."""
        filepath = Path(__file__).parent / ".." / "static" / "components" / folder / filename
        
        if not filepath.exists():
            print(f"Warning: File not found: {filepath}")
            return box(-5, -5, 5, 5)  # Fallback
        
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Namespace de SVG
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            
            all_paths = []
            
            # Extraer todos los paths y polígonos del SVG
            for elem in root.iter():
                if elem.tag.endswith('path'):
                    path_data = elem.get('d', '')
                    if path_data:
                        poly = self._parse_svg_path(path_data)
                        if poly and not poly.is_empty:
                            all_paths.append(poly)
                
                elif elem.tag.endswith('polygon') or elem.tag.endswith('polyline'):
                    points_str = elem.get('points', '')
                    if points_str:
                        poly = self._parse_svg_polygon(points_str)
                        if poly and not poly.is_empty:
                            all_paths.append(poly)
                
                elif elem.tag.endswith('rect'):
                    x_attr = float(elem.get('x', 0))
                    y_attr = float(elem.get('y', 0))
                    w = float(elem.get('width', 0))
                    h = float(elem.get('height', 0))
                    if w > 0 and h > 0:
                        rect = box(x_attr, y_attr, x_attr + w, y_attr + h)
                        all_paths.append(rect)
                
                elif elem.tag.endswith('circle'):
                    cx = float(elem.get('cx', 0))
                    cy = float(elem.get('cy', 0))
                    r = float(elem.get('r', 0))
                    if r > 0:
                        circ = Point(cx, cy).buffer(r, resolution=32)
                        all_paths.append(circ)
            
            if not all_paths:
                print(f"Warning: No valid shapes found in {filename}")
                return box(-5, -5, 5, 5)
            
            # Unir todos los polígonos en uno solo
            combined = unary_union(all_paths)
            
            # Convertir de unidades SVG (px) a mm (asumiendo 96 DPI)
            px_to_mm = 25.4 / 96.0
            combined = scale(combined, xfact=px_to_mm, yfact=px_to_mm, origin=(0, 0))
            
            # Escalar según parámetro del usuario
            if scale != 1.0:
                combined = scale(combined, xfact=scale, yfact=scale, origin=(0, 0))
            
            # Rotar
            if rotation != 0:
                combined = rotate(combined, rotation, origin=(0, 0))
            
            # Trasladar a la posición deseada
            combined = translate(combined, xoff=x, yoff=y)
            
            return combined
            
        except (ValueError, IndexError, ET.ParseError) as e:
            print(f"Error loading {filename}: {e}")
            return box(-5, -5, 5, 5)

    def _parse_svg_path(self, path_data: str) -> Polygon | None:
        """Convierte un path SVG (atributo 'd') a polígono de Shapely."""
        # Simplificación: solo maneja comandos básicos (M, L, Z)
        # Para paths complejos, se recomienda exportar desde Corel como polígonos
        try:
            import re
            commands = re.findall(r'([MLZ])([^MLZ]*)', path_data.upper())
            
            points = []
            for cmd, args in commands:
                if cmd == 'M' or cmd == 'L':
                    coords = [float(x) for x in args.split() if x]
                    for i in range(0, len(coords), 2):
                        if i + 1 < len(coords):
                            points.append((coords[i], coords[i+1]))
            
            if len(points) >= 3:
                poly = Polygon(points)
                if poly.is_valid:
                    return poly
                else:
                    return poly.buffer(0)  # Intentar arreglar
            
            return None
        except (ValueError, IndexError):
            return None

    def _parse_svg_polygon(self, points_str: str) -> Polygon | None:
        """Convierte un polygon SVG (atributo 'points') a polígono de Shapely."""
        try:
            coords = [float(x) for x in points_str.replace(',', ' ').split() if x]
            points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
            
            if len(points) >= 3:
                poly = Polygon(points)
                if poly.is_valid:
                    return poly
                else:
                    return poly.buffer(0)
            
            return None
        except (ValueError, IndexError):
            return None

    def render(self):
        # 1. Cargar el componente de Corel
        component = self.load_svg_component(
            self.component_folder,
            self.component_filename,
            self.component_scale,
            self.component_rotation,
            self.component_x,
            self.component_y
        )
        
        # 2. Generar la base (si existe)
        if self.base_shape == "circle":
            base = Point(0, 0).buffer(self.base_size / 2.0, resolution=64)
        elif self.base_shape == "rectangle":
            base = box(-self.base_size/2, -self.base_size/2, 
                      self.base_size/2, self.base_size/2)
        else:
            base = None
        
        # 3. Combinar base + componente (si hay base)
        if base:
            # Asegurar que el componente quepa dentro de la base + margen
            component_bounds = component.bounds
            base_bounds = base.bounds
            
            # Unir las formas
            final_shape = base.union(component)
        else:
            final_shape = component
        
        # 4. Dibujar el resultado
        self.ctx.save()
        
        if final_shape.geom_type == 'Polygon':
            polygons = [final_shape]
        elif final_shape.geom_type == 'MultiPolygon':
            polygons = final_shape.geoms
        else:
            polygons = []
        
        for poly in polygons:
            if poly.is_empty:
                continue
            
            # Dibujar contorno exterior
            self.ctx.moveTo(poly.exterior.coords[0][0], poly.exterior.coords[0][1])
            for x, y in poly.exterior.coords:
                self.ctx.lineTo(x, y)
            self.ctx.closePath()
            
            # Dibujar agujeros (si existen)
            for interior in poly.interiors:
                self.ctx.moveTo(interior.coords[0][0], interior.coords[0][1])
                for x, y in interior.coords:
                    self.ctx.lineTo(x, y)
                self.ctx.closePath()
        
        self.ctx.set_source_rgb(1, 0, 0)  # Rojo para corte
        self.ctx.set_line_width(0.1)
        self.ctx.stroke()
        
        self.ctx.restore()
