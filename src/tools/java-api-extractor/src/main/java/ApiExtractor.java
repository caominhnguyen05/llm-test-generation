import java.io.File;
import java.util.List;
import java.util.Optional;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;

public class ApiExtractor {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: ApiExtractor <JavaFile> <ClassName>");
            System.exit(1);
        }

        File javaFile = new File(args[0]);
        String className = args[1];

        CompilationUnit cu = StaticJavaParser.parse(javaFile);

        Optional<ClassOrInterfaceDeclaration> classDecl =
                cu.findFirst(ClassOrInterfaceDeclaration.class,
                        c -> c.getNameAsString().equals(className));
        Optional<EnumDeclaration> enumDecl =
                cu.findFirst(EnumDeclaration.class,
                        e -> e.getNameAsString().equals(className));

        if (classDecl.isEmpty() && enumDecl.isEmpty()) {
            System.err.println("Could not find class or enum: " + className);
            System.exit(2);
        }

        List<BodyDeclaration<?>> members = classDecl
                .map(ClassOrInterfaceDeclaration::getMembers)
                .orElseGet(() -> enumDecl.get().getMembers());
        List<ConstructorDeclaration> constructors = classDecl
                .map(ClassOrInterfaceDeclaration::getConstructors)
                .orElse(List.of());

        System.out.println("Class: " + className);
        System.out.println();

        System.out.println("Constructors:");
        for (ConstructorDeclaration constructor : constructors) {
            if (constructor.isPublic() || constructor.isProtected()) {
                System.out.println("- " + constructor.getDeclarationAsString(false, false, false));
            }
        }

        System.out.println();
        System.out.println("Methods:");
        for (BodyDeclaration<?> member : members) {
            if (!member.isMethodDeclaration()) {
                continue;
            }
            MethodDeclaration method = member.asMethodDeclaration();
            if (method.isPublic() || method.isProtected()) {
                System.out.println("- " + method.getDeclarationAsString(false, false, false));
            }
        }
    }
}
