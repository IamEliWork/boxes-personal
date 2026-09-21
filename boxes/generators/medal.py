# Archivo: boxes/generators/medal.py
from boxes import Boxes
from shapely.geometry import Point, Polygon
from shapely.affinity import rotate, translate, scale
import math

class MedalGenerator(Boxes):
    """Generador de Medallas con Borde Personalizado y Relieve.
    Ideal para acrílico y MDF. Permite protuberancias (ej. raquetas, estrellas) 
    que sobresalen del círculo base."""
    
    ui_group = "Trofeos y Medallas"

    def __init__(self):
        super().__init__()
        # Parámetros con descripciones claras en español
        self.add_argument(
            "diameter", type=float, default=50.0,
            help="Diámetro principal del cuerpo de la medalla (mm). Para medallas estándar: 50-70mm"
        )
        self.add_argument(
            "thickness", type=float, default=3.0,
            help="Espesor del material (MDF o Acrílico). Afecta el diseño del relieve interior."
        )
        self.add_argument(
            "protrusion_length", type=float, default=15.0,
            help="Cuánto sobresale el elemento decorativo (ej. la raqueta) desde el borde del círculo (mm)"
        )
        self.add_argument(
            "protrusion_width", type=float, default=12.0,
            help="Ancho del elemento decorativo en su base (mm). Mínimo recomendado: 4mm para acrílico"
        )
        self.add_argument(
            "hole_diameter", type=float, default=6.0,
            help="Diámetro del agujero superior para la cinta o cadena (mm)"
        )
        self.add_argument(
            "relief_offset", type=float, default=2.0,
            help="Distancia del borde interior para crear el efecto de relieve o capa de grabado (mm)"
        )
        self.add_argument(
            "protrusion_angle", type=float, default=0.0,
            help="Ángulo de rotación del elemento decorativo (grados). 0 = arriba"
        )

    def render(self):
        d = self.diameter
        t = self.thickness
        p_len = self.protrusion_length
        p_wid = self.protrusion_width
        hole = self.hole_diameter
        offset = self.relief_offset
        angle = self.protrusion_angle

        self.ctx.save()
        
        # 1. CREACIÓN DE LA FORMA BASE CON SHAPELY
        base_circle = Point(0, 0).buffer(d / 2.0, resolution=64)
        
        # Protuberancia (forma elipsoidal para simular raqueta o elemento similar)
        protrusion = Point(0, d/2.0 + p_len/2.0).buffer(1, resolution=16)
        protrusion = scale(protrusion, xfact=p_wid/2.0, yfact=p_len, origin=(0, d/2.0 + p_len/2.0))
        
        # Rotar si es necesario
        if angle != 0:
            protrusion = rotate(protrusion, angle, origin=(0, 0))
        
        # Unir el círculo y la protuberancia (elimina líneas internas)
        final_shape = base_circle.union(protrusion)
        
        # 2. DIBUJAR EL CORTE EXTERIOR
        self.ctx.moveTo(final_shape.exterior.coords[0][0], final_shape.exterior.coords[0][1])
        for x, y in final_shape.exterior.coords:
            self.ctx.lineTo(x, y)
        self.ctx.closePath()
        self.ctx.stroke()

        # 3. DIBUJAR EL AGUJERO DE LA CINTA
        hole_y = (d / 2.0) + p_len - (p_len / 3.0)
        self.hole(0, hole_y, hole/2.0)

        # 4. DIBUJAR LA LÍNEA DE RELIEVE / GRABADO INTERIOR
        inner_shape = final_shape.buffer(-offset, resolution=32)
        
        if not inner_shape.is_empty:
            self.ctx.set_source_rgb(0, 0, 1) # Azul para grabado/corte interior
            self.ctx.set_line_width(0.1)
            if inner_shape.geom_type == 'Polygon':
                self.ctx.moveTo(inner_shape.exterior.coords[0][0], inner_shape.exterior.coords[0][1])
                for x, y in inner_shape.exterior.coords:
                    self.ctx.lineTo(x, y)
                self.ctx.closePath()
                self.ctx.stroke()
            
            # Texto central (opcional)
            self.ctx.set_source_rgb(0, 0, 0)
            self.text("LOGO", 0, 0, align="center", fontsize=8)

        self.ctx.restore()
