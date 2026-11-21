# Редактирование по команде (FLUX.3 Klein edit)

Target model: instruction-based image editor. The input image is referred to as <ref_image_0> (second reference — <ref_image_1>).
- prompt = one clear imperative instruction: what to change, and explicitly what to keep ("Keep the person's face, pose and the background unchanged.").
- Be concrete about the change (color, material, position, lighting, time of day).
- For "character" requests (same person in a new scene): "Photo of the same person from <ref_image_0> ..." then describe the new scene.
- negative: "".
