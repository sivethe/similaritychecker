/// Inherit from this class if your expression takes a fixed number of arguments.
template <typename SubClass, int NArgs>
class ExpressionFixedArity : public ExpressionNaryBase<SubClass> {
public:
    explicit ExpressionFixedArity(ExpressionContext* const expCtx)
        : ExpressionNaryBase<SubClass>(expCtx) {}
    ExpressionFixedArity(ExpressionContext* const expCtx, Expression::ExpressionVector&& children)
        : ExpressionNaryBase<SubClass>(expCtx, std::move(children)) {}

    void validateChildren() const override {
        uassert(16020,
                str::stream() << "Expression " << this->getOpName() << " takes exactly " << NArgs
                              << " arguments. " << this->_children.size() << " were passed in.",
                this->_children.size() == NArgs);
    }
};