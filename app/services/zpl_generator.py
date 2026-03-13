class ZPLGenerator:

    def generate(self, elements):
        zpl = ["^XA"]

        for el in elements:
            if el["type"] == "rect":
                zpl.append(self.rect(el))

            elif el["type"] == "text":
                zpl.append(self.text(el))

        zpl.append("^XZ")
        return "\n".join(zpl)

    def rect(self, el):
        return f'^FO{int(el["x"])},{int(el["y"])}^GB{int(el["width"])},{int(el["height"])},{int(el["border_width"])}^FS'

    def text(self, el):
        text = el.get("design_system_value") or el.get("text", "")
        size = int(el.get("font_size", 10))

        return f'^FO{int(el["x"])},{int(el["y"])}^A0N,{size},{size}^FD{text}^FS'