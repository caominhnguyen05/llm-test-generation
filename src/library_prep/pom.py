from xml.sax.saxutils import escape

from pipeline.config import LibConfig


def minimal_pom_xml(config: LibConfig) -> str:
    group_id = escape(config.group_id)
    artifact_id = escape(config.artifact_id)
    version = escape(config.version)

    return f"""<?xml version='1.0' encoding='utf-8'?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>llm.generated.tests</groupId>
    <artifactId>{artifact_id}-llm-tests</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    <properties>
        <argLine />
        <maven.compiler.release>8</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    <dependencies>
        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{version}</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.mockito</groupId>
            <artifactId>mockito-core</artifactId>
            <version>4.11.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <testSourceDirectory>src/test/java</testSourceDirectory>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <release>8</release>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
                <configuration>
                    <argLine>@{{argLine}}</argLine>
                    <includes>
                        <include>**/*Test.java</include>
                    </includes>
                </configuration>
                <dependencies>
                    <dependency>
                        <groupId>org.apache.maven.surefire</groupId>
                        <artifactId>surefire-junit4</artifactId>
                        <version>3.2.5</version>
                    </dependency>
                </dependencies>
            </plugin>
        </plugins>
    </build>
</project>
"""


def create_minimal_pom(config: LibConfig) -> bool:
    pom_path = config.library_path / "pom.xml"

    try:
        pom_path.parent.mkdir(parents=True, exist_ok=True)
        pom_path.write_text(minimal_pom_xml(config), encoding="utf-8")
        return True
    except OSError as exc:
        print(f"Failed to create pom.xml for {config.library}: {exc}")
        return False