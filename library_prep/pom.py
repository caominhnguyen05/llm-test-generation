import xml.etree.ElementTree as ET

from pipeline.config import PipelineConfig
from library_prep.config import FIXED_DEPENDENCIES, FIXED_PLUGINS


POM_NS = "http://maven.apache.org/POM/4.0.0"
DEFAULT_JAVA_VERSION = "8"
COMPILER_PLUGIN_VERSION = "3.11.0"

ET.register_namespace("", POM_NS)


def tag(name: str) -> str:
    return f"{{{POM_NS}}}{name}"


def set_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    element = ET.SubElement(parent, tag(name))
    element.text = value
    return element


def parse_pom_block(xml: str) -> ET.Element:
    return ET.fromstring(f'<snippet xmlns="{POM_NS}">{xml}</snippet>')[0]


def create_minimal_pom(config: PipelineConfig) -> bool:
    project = ET.Element(tag("project"))
    project.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    project.set(
        "xsi:schemaLocation",
        "http://maven.apache.org/POM/4.0.0 "
        "http://maven.apache.org/xsd/maven-4.0.0.xsd",
    )

    for name, value in (
        ("modelVersion", "4.0.0"),
        ("groupId", "llm.generated.tests"),
        ("artifactId", f"{config.artifact_id}-llm-tests"),
        ("version", "1.0.0"),
        ("packaging", "jar"),
    ):
        set_text(project, name, value)

    properties = ET.SubElement(project, tag("properties"))
    set_text(properties, "argLine", "")
    set_text(properties, "maven.compiler.release", DEFAULT_JAVA_VERSION)
    set_text(properties, "project.build.sourceEncoding", "UTF-8")

    dependencies = ET.SubElement(project, tag("dependencies"))

    library_dependency = ET.SubElement(dependencies, tag("dependency"))
    set_text(library_dependency, "groupId", config.group_id)
    set_text(library_dependency, "artifactId", config.artifact_id)
    set_text(library_dependency, "version", config.version)

    for dependency_xml in FIXED_DEPENDENCIES:
        dependencies.append(parse_pom_block(dependency_xml))

    build = ET.SubElement(project, tag("build"))
    set_text(build, "testSourceDirectory", "src/test/java")

    plugins = ET.SubElement(build, tag("plugins"))

    compiler_plugin = ET.SubElement(plugins, tag("plugin"))
    set_text(compiler_plugin, "groupId", "org.apache.maven.plugins")
    set_text(compiler_plugin, "artifactId", "maven-compiler-plugin")
    set_text(compiler_plugin, "version", COMPILER_PLUGIN_VERSION)

    compiler_config = ET.SubElement(compiler_plugin, tag("configuration"))
    set_text(compiler_config, "release", DEFAULT_JAVA_VERSION)

    for plugin_xml in FIXED_PLUGINS:
        plugins.append(parse_pom_block(plugin_xml))

    tree = ET.ElementTree(project)
    ET.indent(tree, space="    ")
    tree.write(config.library_path / "pom.xml", encoding="utf-8", xml_declaration=True)

    return True