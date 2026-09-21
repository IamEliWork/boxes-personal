# Archivo: boxes/generators/custom_silhouette.py
from pathlib import Path
import cv2
import numpy as np
from boxes import Boxes
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.affinity import translate, scale, rotate

class CustomSilhouetteGenerator(Boxes):
    """Generador de Medallas/Trofeos con Silueta de Imagen PNG Protruyente.
    Convierte un PNG en un contorno de corte y lo fusiona con una base geométrica."""
    
    ui_group = "Trofeos y Medallas"

    def __init__(self):
        super().__init__()
        self.argparser.add_argument(
            "--base_shape", type=str, default="circle", choices=["circle", "rectangle"],
            help="Forma base del trofeo/medalla."
        )
        self.argparser.add_argument(
            "--base_size", type=float, default=60.0,
            help="Diámetro (si es círculo) o lado (si es cuadrado) de la base (mm)."
        )
        self.argparser.add_argument(
            "--image_filename", type=str, default="bailarina.png",
            help="Nombre del archivo PNG en 'static/images/'. Debe tener fondo transparente o ser blanco/negro."
        )
        self.argparser.add_argument(
            "--image_scale", type=float, default=1.0,
            help="Escala de la imagen (1.0 = tamaño original del PNG en px a mm). Ajustar para que encaje."
        )
        self.argparser.add_argument(
            "--image_rotation", type=float, default=0.0,
            help="Rotación de la silueta antes de fusionarla (grados)."
        )
        self.argparser.add_argument(
            "--protrusion_offset", type=float, default=10.0,
            help="Cuánto debe sobresalir la imagen del borde base (mm)."
        )
        self.argparser.add_argument(
            "--min_neck_width", type=float, default=4.0,
            help="Ancho mínimo de seguridad en la unión para evitar roturas (mm). ¡Crítico para acrílico!"
        )
        self.argparser.add_argument(
            "--simplify_tolerance", type=float, default=0.5,
            help="Suavizado del contorno. Mayor valor = menos nodos = corte más rápido y limpio."
        )

    def get_image_contour(self, filename: str, scale: float, offset: float) -> Polygon | None:
        """Procesa el PNG y devuelve un polígono de Shapely."""
        filepath = Path(__file__).parent / ".." / "static" / "images" / filename
        
        if not filepath.exists():
            print(f"Warning: File not found: {filepath}")
            return box(-10, -10, 10, 10)

        try:
            img = cv2.imread(str(filepath), cv2.IMREAD_UNCHANGED)
            if img is None:
                print(f"Error: Failed to load image: {filepath}")
                return box(-10, -10, 10, 10)
                
            # Manejar canal alfa (transparencia)
            if len(img.shape) == 3 and img.shape[2] == 4:
                alpha = img[:, :, 3]
                _, thresh = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
            else:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                print(f"Warning: No contours found in {filename}")
                return box(-10, -10, 10, 10)

            largest_contour = max(contours, key=cv2.contourArea)
            
            # Convertir a coordenadas de Shapely (escalando de px a mm)
            points = [(pt[0][0] * scale, -pt[0][1] * scale) for pt in largest_contour]
            poly = Polygon(points)
            
            # Simplificar para evitar miles de nodos
            poly = poly.simplify(self.simplify_tolerance, preserve_topology=True)
            
            # Centrar y rotar
            centroid = poly.centroid
            poly = translate(poly, xoff=-centroid.x, yoff=-centroid.y)
            
            if self.image_rotation != 0:
                poly = rotate(poly, self.image_rotation, origin=(0, 0))
            
            # Desplazar para que sobresalga
            offset_y = (self.base_size / 2.0) + offset
            poly = translate(poly, yoff=offset_y)
            
            return poly
        except (cv2.error, ValueError, IndexError) as e:
            print(f"Error processing image {filename}: {e}")
            return box(-10, -10, 10, 10)

    def render(self):
        # 1. Generar forma base
        if self.base_shape == "circle":
            base_poly = Point(0, 0).buffer(self.base_size / 2.0, resolution=64)
        else:
            base_poly = box(-self.base_size/2, -self.base_size/2, self.base_size/2, self.base_size/2)

        # 2. Obtener y procesar la silueta
        silhouette_poly = self.get_image_contour(
            self.image_filename, 
            self.image_scale, 
            self.protrusion_offset
        )

        # 3. UNIÓN GEOMÉTRICA (elimina líneas internas)
        final_shape = base_poly.union(silhouette_poly)

        # 4. Engrosar el "cuello" de la unión para evitar fragilidad
        if self.min_neck_width > 0:
            final_shape = final_shape.buffer(self.min_neck_width / 2.0, resolution=16)
            final_shape = final_shape.buffer(-self.min_neck_width / 2.0, resolution=16)

        # 5. Dibujar en el contexto SVG
        self.ctx.save()
        self.ctx.moveTo(final_shape.exterior.coords[0][0], final_shape.exterior.coords[0][1])
        for x, y in final_shape.exterior.coords:
            self.ctx.lineTo(x, y)
        self.ctx.closePath()
        
        self.ctx.set_source_rgb(1, 0, 0) # Rojo para corte
        self.ctx.set_line_width(0.1)
        self.ctx.stroke()

        # 6. Agujero para cinta si es medalla circular
        if self.base_shape == "circle":
            self.hole(0, (self.base_size / 2.0) + self.protrusion_offset - 10, 3.0)

        self.ctx.restore()
